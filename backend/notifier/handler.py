"""
Notifier Lambda, triggered by each RSVP event the RSVP Lambda writes to the
RSVP_BUCKET S3 bucket (rsvps/*.json).

Each event updates the invitation's rows in the Google Sheet (see sheets.py), is
emailed to us (see notification.py), and is confirmed to the guests (see
confirmation.py). The SSM SecureString GOOGLE_SHEET_PARAMETER holds
{"sheet_id": ..., "service_account_key": {...}}.
"""

import json
import os
import urllib.parse

import boto3

from confirmation import send_confirmation
from notification import RsvpNotification
from sheets import GuestSheet

RSVP_BUCKET = os.environ["RSVP_BUCKET"]

s3 = boto3.client("s3")
google_sheet = json.loads(
    boto3.client("ssm").get_parameter(
        Name=os.environ["GOOGLE_SHEET_PARAMETER"], WithDecryption=True
    )["Parameter"]["Value"]
)


def lambda_handler(event, _context):
    """
    Read the RSVP event named by the S3 notification, update the Google sheet, email
    us the RSVP updates, and email the guests a confirmation. An update where nothing
    changed is skipped.
    """
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    obj = s3.get_object(Bucket=RSVP_BUCKET, Key=key)
    rsvp_event = json.loads(obj["Body"].read())
    notification = RsvpNotification(rsvp_event)
    if rsvp_event["previous"] and not notification.changes():
        return

    GuestSheet(google_sheet["sheet_id"], google_sheet["service_account_key"]).apply(
        rsvp_event
    )
    notification.send()
    send_confirmation(rsvp_event)
