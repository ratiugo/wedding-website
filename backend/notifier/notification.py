"""
The email we get for each RSVP, sent through SES from SENDER_NAME <SENDER_EMAIL> to
the comma-separated RECIPIENT_EMAILS.

The subject says who responded and how many are coming. The body lists what changed
(for an updated RSVP), who's coming and who isn't, their note, the invite code and
when they responded. It's sent as HTML styled like the save-the-date card, with the
same content as plain text for email apps that don't show HTML.
"""

import os
from datetime import datetime
from email.utils import formataddr
from html import escape
from zoneinfo import ZoneInfo

import card
import mail

TIMEZONE = ZoneInfo("America/Vancouver")
SENDER_NAME = os.environ["SENDER_NAME"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RECIPIENT_EMAILS = os.environ["RECIPIENT_EMAILS"].split(",")


class RsvpNotification:
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
        Send the email.
        """
        mail.send(
            formataddr((SENDER_NAME, SENDER_EMAIL)),
            RECIPIENT_EMAILS,
            mail.content(self.subject(), self.body(), self.html()),
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
                f"  • {guest['name']}{card.details(guest)}" for guest in self.coming
            )
            lines.append("")
        if self.not_coming:
            lines.append(f"Not coming ({len(self.not_coming)})")
            lines.extend(f"  • {guest['name']}" for guest in self.not_coming)
            lines.append("")
        if self.invitation["notes"]:
            lines.extend(["Their note:", f"  {self.invitation['notes']}", ""])

        lines.append(f"Invite code: {self.invitation['invite_code']}")
        lines.append(f"Responded: {self.responded()}")
        return "\n".join(lines)

    def html(self):
        """
        The email's HTML body: the same content as body(), styled like the
        save-the-date card. Text from guests is escaped.
        """
        sections = []
        if self.previous:
            sections.append(card.section("What changed", self.changes()))
        if self.coming:
            sections.append(
                card.section(
                    f"Coming ({len(self.coming)})",
                    [guest["name"] + card.details(guest) for guest in self.coming],
                )
            )
        if self.not_coming:
            sections.append(
                card.section(
                    f"Not coming ({len(self.not_coming)})",
                    [guest["name"] for guest in self.not_coming],
                )
            )
        if self.invitation["notes"]:
            sections.append(card.quote(escape(self.invitation["notes"])))

        guests = len(self.invitation["guests"])
        return card.card(
            "".join(sections),
            eyebrow="Updated RSVP" if self.previous else "New RSVP",
            title=card.ampersand(escape(self.label)),
            subtitle=f"{len(self.coming)} of {guests} coming",
            footer=escape(
                f"Invite code {self.invitation['invite_code']} · "
                f"Responded {self.responded()}"
            ),
        )

    def responded(self):
        """
        When they responded, in Vancouver time, like "Sat Oct 24, 2026 at 6:00 PM PDT".
        """
        responded = datetime.fromisoformat(self.invitation["responded_at"])
        return f"{responded.astimezone(TIMEZONE):%a %b %-d, %Y at %-I:%M %p %Z}"

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
