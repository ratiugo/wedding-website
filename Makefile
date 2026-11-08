# Local development. Run `make start`, then open http://localhost:8080.

# Use docker from PATH, falling back to Docker Desktop's bundled CLI.
DOCKER ?= $(shell command -v docker || echo /Applications/Docker.app/Contents/Resources/bin/docker)
# docker runs helpers (like docker-credential-desktop) from the same folder.
export PATH := $(dir $(DOCKER)):$(PATH)
COMPOSE = $(DOCKER) compose -f backend/docker-compose.yml

# Local settings (Google Sheet ids, update sender and reply-to), if present.
-include backend/.env
# Environment for sheet-setup, load-guests and send-update: dev (default) or prod.
ENV ?= dev
SITE_URL = https://$(if $(filter prod,$(ENV)),tessandcolton.com,dev.tessandcolton.com)

.PHONY: start stop sheet-setup load-guests send-update test format lint

# Start the RSVP Lambda and fake AWS, create the bucket and the example invitations,
# then serve the site and API (Ctrl+C to stop).
start:
	$(COMPOSE) up --build -d --wait --remove-orphans
	$(COMPOSE) exec rsvp python /scripts/local_aws.py
	python3 backend/scripts/dev_server.py

# Stop the containers. The fake AWS keeps nothing, so the next start begins with just
# the example invitations again.
stop:
	$(COMPOSE) down

# Create the Guests and Summary tabs in dev's Google Sheet, if missing, or in prod's
# with `make sheet-setup ENV=prod` (sheet ids in backend/.env).
sheet-setup:
	GOOGLE_SHEET_ID=$(if $(filter prod,$(ENV)),$(PROD_GOOGLE_SHEET_ID),$(DEV_GOOGLE_SHEET_ID)) \
		$(COMPOSE) run --rm --build sheet-setup

# Add the invitations in dev's guest list (backend/data/guests.dev.csv) that aren't in
# its table yet, or prod's (guests.csv) with ENV=prod, after showing them and asking.
# Then writes each invitation's code and RSVP link to backend/data/codes.<env>.csv.
load-guests:
	$(COMPOSE) run --rm --build \
		-e INVITATIONS_TABLE=wedding-$(ENV)-invitations \
		-e SITE_URL=$(SITE_URL) \
		load-guests /data/$(if $(filter prod,$(ENV)),guests.csv,guests.dev.csv) \
		--codes /data/codes.$(ENV).csv

# Send the update in FILE, a message file in updates/ (see scripts/send_update.py).
# Uses UPDATE_SENDER and REPLY_TO from backend/.env.
send-update:
	$(if $(FILE),,$(error Set FILE to a message file, like FILE=updates/itinerary.txt))
	$(if $(wildcard $(FILE)),,$(error No message file at $(FILE)))
	mkdir -p updates
	$(COMPOSE) run --rm --build \
		-e INVITATIONS_TABLE=wedding-$(ENV)-invitations \
		-e SITE_URL=$(SITE_URL) \
		-e 'SENDER=$(UPDATE_SENDER)' \
		-e REPLY_TO=$(REPLY_TO) \
		send-update /updates/$(notdir $(FILE)) \
		--preview /updates/$(basename $(notdir $(FILE))).preview.html

# Run the backend tests (the database, S3, SES and Google Sheets are all mocked).
test:
	$(COMPOSE) run --rm --build rsvp-test
	$(COMPOSE) run --rm --build notifier-test

# Format the backend Python with black.
format:
	$(COMPOSE) run --rm --build --no-deps --entrypoint black rsvp-test .

# Check formatting (black) and code quality (pylint) without changing anything.
lint:
	$(COMPOSE) run --rm --build --no-deps --entrypoint black rsvp-test --check .
	$(COMPOSE) run --rm --no-deps --entrypoint pylint rsvp-test rsvp shared scripts --ignore=setup_sheet.py
	$(COMPOSE) run --rm --build --entrypoint pylint notifier-test notifier scripts/setup_sheet.py
