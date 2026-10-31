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

import boto3

TIMEZONE = ZoneInfo("America/Vancouver")
SENDER_NAME = os.environ["SENDER_NAME"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
RECIPIENT_EMAILS = os.environ["RECIPIENT_EMAILS"].split(",")

# The save-the-date card's look, with inline styles because email apps ignore most
# stylesheets. Gmail doesn't load web fonts, so it shows Georgia and Arial instead.
SERIF = "'Cormorant Garamond', Georgia, serif"
SANS = "Jost, 'Helvetica Neue', Arial, sans-serif"

HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;1,400&family=Jost&display=swap" rel="stylesheet">
</head>
<body style="margin: 0; padding: 0; background: #efe9f1;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: #efe9f1;">
<tr><td align="center" style="padding: 32px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 560px; background: #fbf9f4; border: 1px solid #9aab8a;">
  <tr><td style="padding: 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid #9aab8a;">
    <tr><td align="center" style="padding: 40px 28px; font-family: {serif}; color: #3e3a36;">
      <p style="margin: 0; font-family: {sans}; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: #6c7d5e;">{eyebrow}</p>
      <h1 style="margin: 12px 0 4px; font-family: {serif}; font-size: 34px; font-weight: normal; line-height: 1.2;">{label}</h1>
      <p style="margin: 0; font-size: 18px; font-style: italic; color: #7a736b;">{summary}</p>
      <hr style="width: 64px; margin: 28px auto; border: 0; border-top: 1px solid #9aab8a;">
      {sections}
      <p style="margin: 32px 0 0; font-family: {sans}; font-size: 11px; letter-spacing: 1px; color: #7a736b;">{footer}</p>
    </td></tr>
    </table>
  </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""

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
        Send the email, unless it's an update where nothing changed.
        """
        if self.previous and not self.changes():
            return
        ses.send_email(
            FromEmailAddress=formataddr((SENDER_NAME, SENDER_EMAIL)),
            Destination={"ToAddresses": RECIPIENT_EMAILS},
            Content={
                "Simple": {
                    "Subject": {"Data": self.subject(), "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": self.body(), "Charset": "UTF-8"},
                        "Html": {"Data": self.html(), "Charset": "UTF-8"},
                    },
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
            sections.append(section("What changed", self.changes()))
        if self.coming:
            sections.append(
                section(
                    f"Coming ({len(self.coming)})",
                    [guest["name"] + details(guest) for guest in self.coming],
                )
            )
        if self.not_coming:
            sections.append(
                section(
                    f"Not coming ({len(self.not_coming)})",
                    [guest["name"] for guest in self.not_coming],
                )
            )
        if self.invitation["notes"]:
            note = escape(self.invitation["notes"])
            sections.append(
                '<p style="margin: 8px 0 0; font-size: 20px; font-style: italic;'
                f' color: #9a84b5;">&ldquo;{note}&rdquo;</p>'
            )

        guests = len(self.invitation["guests"])
        return HTML.format(
            serif=SERIF,
            sans=SANS,
            eyebrow="Updated RSVP" if self.previous else "New RSVP",
            # The ampersand in lilac italic, as on the save-the-date.
            label=escape(self.label).replace(
                "&amp;",
                '<span style="font-style: italic; color: #9a84b5;">&amp;</span>',
            ),
            summary=f"{len(self.coming)} of {guests} coming",
            sections="".join(sections),
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


def details(guest):
    """
    Extras for a guest who is coming, like " (child, dietary: Vegan)".
    """
    extras = ["child"] if guest["child"] else []
    if guest["dietary"]:
        extras.append(f"dietary: {guest['dietary']}")
    return f" ({', '.join(extras)})" if extras else ""


def section(title, lines):
    """
    A titled list for the HTML email, like "Coming (2)" and a line per guest.
    """
    heading = (
        f'<p style="margin: 24px 0 8px; font-family: {SANS}; font-size: 11px;'
        ' letter-spacing: 3px; text-transform: uppercase; color: #6c7d5e;">'
        f"{escape(title)}</p>"
    )
    items = "".join(
        f'<p style="margin: 4px 0; font-size: 18px;">{escape(line)}</p>'
        for line in lines
    )
    return heading + items
