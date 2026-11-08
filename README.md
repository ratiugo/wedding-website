# Tess & Colton's Wedding

Website for our wedding: a static site with an RSVP form, backed by two Python Lambdas.

Guests enter the invite code from their card on the RSVP page. The RSVP Lambda saves
their answers to DynamoDB and writes an event to S3, which triggers the notifier
Lambda to update our Google Sheet and email us.

## Layout

```
frontend/              The site: index.html, rsvp.html, css/, js/
backend/rsvp/          RSVP Lambda: handler.py (API routes), invitation.py, db.py
backend/notifier/      Notifier Lambda: handler.py, notification.py, confirmation.py, card.py, mail.py, sheets.py
backend/shared/        Code both Lambdas include: events.py (the weekend events guests RSVP to),
                       invite_list.py (the planning workbook's Invite list columns)
backend/scripts/       dev_server.py (local site + API), local_aws.py (local bucket, table, examples),
                       setup_sheet.py (Invite list columns, RSVP summary tab),
                       load_guests.py (Invite list -> invitations, codes back into the sheet),
                       send_update.py (update emails to guests)
backend/data/          guests.example.csv (local example guests, in the Invite list's layout)
backend/docker-compose.yml   Local services, plus the test images
```

## Running locally

Requires Docker.

```sh
make start        # start the Lambda and fake AWS (S3, DynamoDB), then serve http://localhost:8080
make stop         # stop the containers; the next start begins with the example guests again
make sheet-setup  # add the code and RSVP columns and RSVP summary to dev's planning workbook;
                  # ENV=prod for the real one (needs backend/.env)
make load-guests  # add new invitations from dev's Invite list to dev's table, after asking, and
                  # write their codes into the sheet; ENV=prod for the real list
make send-update FILE=updates/<name>.txt
                  # email an update to dev's guests, after showing who and asking;
                  # ENV=prod for real guests (message format in scripts/send_update.py)
```

The local database starts with the example invitations in
`backend/data/guests.example.csv`. Their codes are random, so `make start` prints each
one's RSVP link.

## Tests

```sh
make test    # pytest for both Lambdas (the database, S3, SES and Google are mocked)
make format  # format the Python with black
make lint    # check black and pylint
```
