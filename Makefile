# Local development. Run `make start`, then open http://localhost:8080.

# Use docker from PATH, falling back to Docker Desktop's bundled CLI.
DOCKER ?= $(shell command -v docker || echo /Applications/Docker.app/Contents/Resources/bin/docker)
# docker runs helpers (like docker-credential-desktop) from the same folder.
export PATH := $(dir $(DOCKER)):$(PATH)
COMPOSE = $(DOCKER) compose -f backend/docker-compose.yml

.PHONY: start stop sheet-setup test format lint

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

# Create the Google Sheet's Guests and Summary tabs, if missing (GOOGLE_SHEET_ID in backend/.env).
sheet-setup:
	$(COMPOSE) run --rm --build sheet-setup

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
	$(COMPOSE) run --rm --no-deps --entrypoint pylint rsvp-test rsvp scripts --ignore=setup_sheet.py
	$(COMPOSE) run --rm --build --entrypoint pylint notifier-test notifier scripts/setup_sheet.py
