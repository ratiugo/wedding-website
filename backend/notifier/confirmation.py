"""
The confirmation email a guest gets for their RSVP, sent through SES from
GUEST_SENDER to the invitation's email in INVITATIONS_TABLE. Replies and bounce
notifications go to REPLY_TO.
"""

import logging
import os
from html import escape

import boto3
from botocore.exceptions import ClientError

import card
import mail

GUEST_SENDER = os.environ["GUEST_SENDER"]
REPLY_TO = os.environ["REPLY_TO"]
SITE_URL = os.environ["SITE_URL"]
FOOTER = "Something not right? Just reply to this email."

logger = logging.getLogger(__name__)
invitations = boto3.resource("dynamodb").Table(os.environ["INVITATIONS_TABLE"])


def send_confirmation(event):
    """
    Email the invitation its RSVP, unless it has no email.

    Failures are logged instead of raised, so the Lambda isn't retried and the sheet
    update and our email aren't repeated.
    """
    invitation = event["invitation"]
    try:
        item = invitations.get_item(Key={"invite_code": invitation["invite_code"]})
        email = item.get("Item", {}).get("email")
        if email:
            mail.send(
                GUEST_SENDER,
                [email],
                mail.content("Your RSVP", text(invitation), html(invitation)),
                reply_to=REPLY_TO,
            )
    except ClientError:
        logger.exception(
            "Failed to send RSVP confirmation for %s", invitation["invite_code"]
        )


def text(invitation):
    """
    The email's plain-text body.
    """
    lines = [f"Hi {invitation['label']},", "", "Thanks for your RSVP!", ""]
    lines += [f"  • {answer}" for answer in answers(invitation)]
    if invitation["notes"]:
        lines += ["", f"Your note: {invitation['notes']}"]
    lines += ["", f"Change your RSVP: {rsvp_url(invitation)}", "", FOOTER]
    return "\n".join(lines)


def html(invitation):
    """
    The email's HTML body, styled like the save-the-date card. Text from guests is
    escaped.
    """
    content = [
        card.paragraph(card.ampersand(escape(f"Hi {invitation['label']},"))),
        card.section("Your RSVP", answers(invitation)),
    ]
    if invitation["notes"]:
        content.append(card.quote(escape(invitation["notes"])))
    content.append(card.button("Change your RSVP", escape(rsvp_url(invitation))))
    return card.card(
        "\n".join(content),
        eyebrow=card.ampersand("Tess &amp; Colton"),
        title="Thanks for your RSVP!",
        footer=FOOTER,
    )


def answers(invitation):
    """
    Each guest's answer, like "Jamie: coming (dietary: Vegan)" or "Alex: not coming".
    """
    return [
        f"{guest['name']}: "
        + ("coming" + card.details(guest) if guest["attending"] else "not coming")
        for guest in invitation["guests"]
    ]


def rsvp_url(invitation):
    """
    The invitation's RSVP page.
    """
    return f"{SITE_URL}/rsvp?invite_code={invitation['invite_code']}"
