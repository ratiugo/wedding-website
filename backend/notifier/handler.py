"""
Notifier Lambda, triggered by each RSVP event the RSVP Lambda writes to the
RSVP_BUCKET S3 bucket (rsvps/*.json).

Each event updates the invitation's rows in the Google Sheet (see sheets.py) and is
emailed to us (see emails.py). The SSM SecureString GOOGLE_SHEET_PARAMETER holds
{"sheet_id": ..., "service_account_key": {...}}.
"""

import json
import os
import urllib.parse

import boto3

from emails import RsvpEmail
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
    Read the RSVP event named by the S3 notification, update the Google sheet and
    email us the RSVP updates.
    """
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    obj = s3.get_object(Bucket=RSVP_BUCKET, Key=key)
    rsvp_event = json.loads(obj["Body"].read())

    GuestSheet(google_sheet["sheet_id"], google_sheet["service_account_key"]).apply(
        rsvp_event
    )
    RsvpEmail(rsvp_event).send()
