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
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from db import Database
from events import EVENTS

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
        self.updates_opt_out = row.get("updates_opt_out", False)

    @classmethod
    def get(cls, invite_code):
        """
        Return the invitation for an invite code, or None if there isn't one.

        Case and anything but letters and digits are ignored, since cards print
        codes like H7KM-3QPX and links can pick up punctuation when pasted (a
        trailing comma or period). Codes that can't be valid (anything but eight
        letters and digits) return None without a database lookup.
        """
        invite_code = re.sub(r"[^A-Z0-9]", "", invite_code.upper())
        if len(invite_code) != 8:
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
            database.save_response(
                self.invite_code,
                guests,
                clean(body.get("notes")),
                body.get("updates_opt_out") is True,
            )
        )
        try:
            saved.publish(previous=self if self.responded_at else None)
        except (BotoCoreError, ClientError):
            logger.exception("Failed to publish RSVP event for %s", self.invite_code)
        return saved

    def opt_out(self):
        """
        Stop update emails for this invitation. Only the opt-out changes, not the
        answers or when they responded, so it doesn't count as an RSVP.
        """
        database.opt_out(self.invite_code)
        self.updates_opt_out = True

    def validate_answers(self, body):
        """
        Validate a request body's answers and return the guests with them filled in.

        The body must answer for every guest on this invitation, saying whether each
        is attending the wedding, and if so whether they're coming to each of EVENTS,
        and give a name for a plus-one who's coming. Otherwise this raises
        BadRequest, with a message for the guest.

        dietary and events are blank for guests who aren't coming. Only a plus-one's
        name can be changed, and only when one is given.
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

            name = plus_one_name or guest["name"]
            cleaned.append(
                {
                    **guest,
                    "name": name,
                    "attending": attending,
                    "events": event_answers(name, answer) if attending else {},
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

        Each guest contains the fields: id, name, plus_one, child, attending, events
        (answers by event id), dietary. events lists the weekend events to ask about.
        The invitation's email is left out, since anyone with the code can see this.
        """
        return {
            "invite_code": self.invite_code,
            "label": self.label,
            "notes": self.notes,
            "responded_at": self.responded_at,
            "updates_opt_out": self.updates_opt_out,
            "guests": self.guests,
            "events": [{"id": event, "name": name} for event, name in EVENTS.items()],
        }


def event_answers(name, answer):
    """
    The answers for each of EVENTS from a guest's answer in a request body, where
    name is the guest's name.

    Raises BadRequest unless every event is answered true or false.
    """
    events = answer.get("events")
    events = events if isinstance(events, dict) else {}
    for event, title in EVENTS.items():
        if not isinstance(events.get(event), bool):
            raise BadRequest(f"Please say whether {name} is coming to the {title}.")
    return {event: events[event] for event in EVENTS}


def clean(text):
    """
    An optional text answer, stripped and capped at 500 characters.
    """
    return str(text or "").strip()[:500]
