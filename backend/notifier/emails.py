"""
The email we get for each RSVP, sent through SES from SENDER_EMAIL to the
comma-separated RECIPIENT_EMAILS.

The subject says who responded and how many are coming. The body lists what changed
(for an updated RSVP), who's coming and who isn't, their note, the invite code and
when they responded.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

TIMEZONE = ZoneInfo("America/Vancouver")
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RECIPIENT_EMAILS = os.environ["RECIPIENT_EMAILS"].split(",")

ses = boto3.client("sesv2")


class RsvpEmail:
    """
    The email for one RSVP event.
    """

    def __init__(self, event):
        self.invitation = event["invitation"]
        self.previous = event["previous"]
        self.label = self.invitation["label"]
        guests = self.invitation["guests"]
        self.coming = [guest for guest in guests if guest["attending"]]
        self.not_coming = [guest for guest in guests if not guest["attending"]]

    def send(self):
        """
        Send the email as plain text, unless it's an update where nothing changed.
        """
        if self.previous and not self.changes():
            return
        ses.send_email(
            FromEmailAddress=SENDER_EMAIL,
            Destination={"ToAddresses": RECIPIENT_EMAILS},
            Content={
                "Simple": {
                    "Subject": {"Data": self.subject(), "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": self.body(), "Charset": "UTF-8"}},
                }
            },
        )

    def subject(self):
        """
        Who responded, whether it's an update, and how many are coming.
        """
        count = f"{len(self.coming)} of {len(self.invitation['guests'])} coming"
        if self.previous:
            return f"{self.label} updated their RSVP ({count})"
        if self.coming:
            return f"{self.label} just RSVP'd! ({count})"
        return f"{self.label} just RSVP'd (sending their regrets)"

    def body(self):
        """
        The email's plain-text body.
        """
        opening = "updated their RSVP." if self.previous else "just RSVP'd!"
        lines = [f"{self.label} {opening}", ""]
        if self.previous:
            lines.append("What changed")
            lines.extend(f"  • {line}" for line in self.changes())
            lines.append("")
        if self.coming:
            lines.append(f"Coming ({len(self.coming)})")
            lines.extend(
                f"  • {guest['name']}{details(guest)}" for guest in self.coming
            )
            lines.append("")
        if self.not_coming:
            lines.append(f"Not coming ({len(self.not_coming)})")
            lines.extend(f"  • {guest['name']}" for guest in self.not_coming)
            lines.append("")
        if self.invitation["notes"]:
            lines.extend(["Their note:", f"  {self.invitation['notes']}", ""])

        responded = datetime.fromisoformat(self.invitation["responded_at"])
        responded = responded.astimezone(TIMEZONE)
        lines.append(f"Invite code: {self.invitation['invite_code']}")
        lines.append(f"Responded: {responded:%a %b %-d, %Y at %-I:%M %p %Z}")
        return "\n".join(lines)

    def changes(self):
        """
        One line for each thing that changed since the previous response.

        Covers plus-ones being named, attendance, dietary notes (for guests who are
        coming) and the invitation's note. An invitation's guests never change, so
        both snapshots list the same guests in the same order.
        """
        lines = []
        for before, guest in zip(self.previous["guests"], self.invitation["guests"]):
            name = guest["name"]

            if before["name"] != name:
                lines.append(f"{before['name']} is now {name}")

            if before["attending"] != guest["attending"]:
                coming = "is now coming" if guest["attending"] else "can no longer come"
                lines.append(f"{name} {coming}")

            if guest["attending"] and before["dietary"] != guest["dietary"]:
                old, new = before["dietary"] or "none", guest["dietary"] or "none"
                lines.append(f"{name}'s dietary: {old} → {new}")

        old, new = self.previous["notes"], self.invitation["notes"]
        if old != new:
            lines.append(f"Note: {old or 'none'} → {new or 'none'}")

        return lines


def details(guest):
    """
    Extras for a guest who is coming, like " (child, dietary: Vegan)".
    """
    extras = ["child"] if guest["child"] else []
    if guest["dietary"]:
        extras.append(f"dietary: {guest['dietary']}")
    return f" ({', '.join(extras)})" if extras else ""
