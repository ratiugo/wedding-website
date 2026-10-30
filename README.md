# Tess & Colton's Wedding

Website for our wedding: a static site with an RSVP form, backed by two Python Lambdas.

Guests enter the invite code from their card on the RSVP page. The RSVP Lambda saves
their answers to DynamoDB and writes an event to S3, which triggers the notifier
Lambda to update our Google Sheet and email us.

## Layout

```
frontend/              The site: index.html, rsvp.html, css/, js/
backend/rsvp/          RSVP Lambda: handler.py (API routes), invitation.py, db.py
backend/notifier/      Notifier Lambda: handler.py, emails.py, sheets.py
backend/scripts/       dev_server.py (local site + API), local_aws.py (local bucket, table, examples),
                       setup_sheet.py (Google Sheet tabs)
backend/data/          invitations.example.json (local example guests), guests.example.csv
backend/docker-compose.yml   Local services, plus the test images
```

## Running locally

Requires Docker.

```sh
make start        # start the Lambda and fake AWS (S3, DynamoDB), then serve http://localhost:8080
make stop         # stop the containers; the next start begins with the example guests again
make sheet-setup  # create the Google Sheet's tabs (needs backend/.env; see .env.example)
```

The local database starts with three example invitations: invite codes `RIVERA`,
`SHAHPD` and `JAMIE2`.

## Tests

```sh
make test    # pytest for both Lambdas (the database, S3, SES and Google are mocked)
make format  # format the Python with black
make lint    # check black and pylint
```
