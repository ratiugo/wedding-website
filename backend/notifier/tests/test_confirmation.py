"""
Confirmation email tests, with mocks in place of DynamoDB and SES.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import card
import confirmation
from confirmation import send_confirmation
from tests.factories import guest


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    """
    Mock SES, and the table with an email for the invitation.
    """
    monkeypatch.setattr(card, "ses", MagicMock())
    monkeypatch.setattr(confirmation, "invitations", MagicMock())
    confirmation.invitations.get_item.return_value = {
        "Item": {"invite_code": "JAMIE234", "email": "jamie@example.com"}
    }


def invitation(guests, notes=""):
    """
    A sample invitation, as it appears in an RSVP event.
    """
    return {
        "invite_code": "JAMIE234",
        "label": "Jamie",
        "notes": notes,
        "responded_at": "2026-10-25T01:00:00+00:00",
        "guests": guests,
    }


def sent_email():
    """
    The arguments of the one email sent to SES.
    """
    card.ses.send_email.assert_called_once()
    return card.ses.send_email.call_args.kwargs


# The email


def test_the_plain_text_email():
    text = confirmation.text(
        invitation(
            [guest("Jamie", True, dietary="Vegan"), guest("Alex", False)],
            notes="See you there!",
        )
    )

    assert text == "\n".join(
        [
            "Hi Jamie,",
            "",
            "Thanks for your RSVP!",
            "",
            "  • Jamie: coming (dietary: Vegan)",
            "  • Alex: not coming",
            "",
            "Your note: See you there!",
            "",
            "Change your RSVP: https://example.com/rsvp?invite_code=JAMIE234",
            "",
            "Something not right? Just reply to this email.",
        ]
    )


def test_the_html_email_escapes_guest_text():
    html = confirmation.html(invitation([guest("Jamie <b>", True)]))

    assert "Jamie &lt;b&gt;" in html
    assert "<b>" not in html


# Sending


def test_it_goes_to_the_invitations_email():
    send_confirmation(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    )
    assert sent_email()["Destination"] == {"ToAddresses": ["jamie@example.com"]}


def test_replies_and_bounces_go_to_reply_to():
    send_confirmation(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    )

    assert sent_email()["ReplyToAddresses"] == ["us@example.com"]
    assert sent_email()["FeedbackForwardingEmailAddress"] == "us@example.com"


def test_an_invitation_without_an_email_gets_nothing():
    confirmation.invitations.get_item.return_value = {
        "Item": {"invite_code": "JAMIE234", "email": None}
    }

    send_confirmation(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    )

    card.ses.send_email.assert_not_called()


def test_a_failed_send_is_logged_instead_of_raised(caplog):
    card.ses.send_email.side_effect = ClientError(
        {"Error": {"Code": "MessageRejected"}}, "SendEmail"
    )

    send_confirmation(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    )

    assert "Failed to send RSVP confirmation for JAMIE234" in caplog.text
