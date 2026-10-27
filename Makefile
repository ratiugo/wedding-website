# Local development. Run `make start`, then open http://localhost:8080.

# Use docker from PATH, falling back to Docker Desktop's bundled CLI.
DOCKER ?= $(shell command -v docker || echo /Applications/Docker.app/Contents/Resources/bin/docker)
# docker runs helpers (like docker-credential-desktop) from the same folder.
export PATH := $(dir $(DOCKER)):$(PATH)
COMPOSE = $(DOCKER) compose -f backend/docker-compose.yml

.PHONY: start stop reset-db db sheet-setup test format lint

# Start the RSVP Lambda, Postgres and fake S3, create the S3 bucket, then serve the
# site and API (Ctrl+C to stop).
start:
	$(COMPOSE) up --build -d --wait --remove-orphans
	$(COMPOSE) exec rsvp python -c \
		"import boto3, os; boto3.client('s3').create_bucket(Bucket=os.environ['RSVP_BUCKET'])"
	python3 backend/scripts/dev_server.py

# Stop the containers. Data is kept; `$(COMPOSE) down -v` wipes it.
stop:
	$(COMPOSE) down

# Stop the containers and wipe the local database; the next `make start` reloads the
# example guests from backend/data/seed.sql.
reset-db:
	$(COMPOSE) down -v

# Open a SQL prompt on the local database.
db:
	$(COMPOSE) exec postgres psql -U wedding -d wedding

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
