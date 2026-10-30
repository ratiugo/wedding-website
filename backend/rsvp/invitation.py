"""
Invitations for the RSVP form: Invitation.get looks one up by invite code, and
Invitation.respond saves the guests' answers.

Each response (first or updated) is saved to the database, then uploaded to S3 as a
snapshot of the invitation. A separate notifier lambda reads those uploads to email
us and update the wedding planning spreadsheet.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from db import Database

logger = logging.getLogger(__name__)

database = Database(os.environ["INVITATIONS_TABLE"])
s3 = boto3.client("s3")
RSVP_BUCKET = os.environ.get("RSVP_BUCKET")


class BadRequest(Exception):
    """
    Invalid answers from a guest; the message is shown to them.
    """


class Invitation:
    """
    One invitation (one card and invite code) and its guests.
    """

    def __init__(self, row):
        """
        Hold an invitation's fields, from the dict Database.get_invitation returns.
        """
        self.invite_code = row["invite_code"]
        self.label = row["label"]
        self.notes = row["notes"]
        self.responded_at = row["responded_at"]
        self.guests = row["guests"]

    @classmethod
    def get(cls, invite_code):
        """
        Return the invitation for an invite code, or None if there isn't one.

        Spaces and case are ignored. Codes that can't be valid (anything but six
        letters and digits) return None without a database lookup.
        """
        invite_code = "".join(invite_code.split()).upper()
        if len(invite_code) != 6 or not invite_code.isalnum():
            return None
        row = database.get_invitation(invite_code)
        return cls(row) if row else None

    def respond(self, body):
        """
        Save the guests' answers from a request body and return the saved invitation.

        Raises BadRequest if the answers don't fit the invitation. The saved
        invitation is uploaded to S3 as an "rsvp" event; if that fails it's logged
        instead, since the answers are already saved.
        """
        guests = self.validate_answers(body)
        saved = Invitation(
            database.save_response(self.invite_code, guests, clean(body.get("notes")))
        )
        try:
            saved.publish(previous=self if self.responded_at else None)
        except (BotoCoreError, ClientError):
            logger.exception("Failed to publish RSVP event for %s", self.invite_code)
        return saved

    def validate_answers(self, body):
        """
        Validate a request body's answers and return the guests with them filled in.

        The body must answer for every guest on this invitation, saying whether each
        is attending, and give a name for a plus-one who's coming. Otherwise this
        raises BadRequest, with a message for the guest.

        dietary is blank for guests who aren't coming. Only a plus-one's name can be
        changed, and only when one is given.
        """
        try:
            answers = {answer["id"]: answer for answer in body["guests"]}
        except (KeyError, TypeError) as e:
            raise BadRequest("Expected {'guests': [{'id': ...}, ...]}.") from e
        if answers.keys() != {guest["id"] for guest in self.guests}:
            raise BadRequest("Please answer for every guest on the invitation.")

        cleaned = []
        for guest in self.guests:
            answer = answers[guest["id"]]
            attending = answer.get("attending")

            if not isinstance(attending, bool):
                raise BadRequest(f"Please say whether {guest['name']} is attending.")

            plus_one_name = clean(answer.get("name")) if guest["plus_one"] else ""
            if guest["plus_one"] and attending and not plus_one_name:
                raise BadRequest("Please tell us your guest's name.")

            cleaned.append(
                {
                    **guest,
                    "name": plus_one_name or guest["name"],
                    "attending": attending,
                    "dietary": clean(answer.get("dietary")) if attending else "",
                }
            )
        return cleaned

    def publish(self, previous):
        """
        Write an RSVP event about this invitation to S3.

        The key is rsvps/<invite_code>/<UTC timestamp>.json, so an invitation's
        events sort by time; the notifier's sheet sync relies on that. previous is
        the invitation before this response, or None if it's the first.
        """
        published_at = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%S.%fZ}"
        event = {
            "published_at": published_at,
            "invitation": self.view(),
            "previous": previous.view() if previous else None,
        }
        s3.put_object(
            Bucket=RSVP_BUCKET,
            Key=f"rsvps/{self.invite_code}/{published_at}.json",
            Body=json.dumps(event),
            ContentType="application/json",
        )

    def view(self):
        """
        What a guest is allowed to see about their own invitation, as JSON data.

        Each guest contains the fields: id, name, plus_one, child, attending, dietary.
        """
        return {
            "invite_code": self.invite_code,
            "label": self.label,
            "notes": self.notes,
            "responded_at": self.responded_at,
            "guests": self.guests,
        }


def clean(text):
    """
    An optional text answer, stripped and capped at 500 characters.
    """
    return str(text or "").strip()[:500]
