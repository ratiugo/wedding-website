"""
Confirmation email tests, with mocks in place of DynamoDB and SES.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import confirmation
import mail
from confirmation import send_confirmation

INVITATION = {
    "invite_code": "JAMIE234",
    "label": "Jamie",
    "notes": "See you there!",
    "responded_at": "2026-10-25T01:00:00+00:00",
    "guests": [
        {"name": "Jamie", "attending": True, "child": False, "dietary": "Vegan"},
        {"name": "Alex", "attending": False, "child": False, "dietary": ""},
    ],
}
EVENT = {"invitation": INVITATION, "previous": None}


@pytest.fixture(autouse=True)
def mocks(monkeypatch):
    """
    Mock SES, and the table with an email for the invitation.
    """
    monkeypatch.setattr(mail, "ses", MagicMock())
    monkeypatch.setattr(confirmation, "invitations", MagicMock())
    confirmation.invitations.get_item.return_value = {
        "Item": {"invite_code": "JAMIE234", "email": "jamie@example.com"}
    }


def sent_email():
    """
    The arguments of the one email sent to SES.
    """
    mail.ses.send_email.assert_called_once()
    return mail.ses.send_email.call_args.kwargs


def test_the_plain_text_email():
    assert confirmation.text(INVITATION) == "\n".join(
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


def test_a_link_in_a_guests_note_isnt_a_real_link():
    note = '<a href="https://spam.example">Click me</a>'
    html = confirmation.html({**INVITATION, "notes": note})
    assert note not in html


def test_it_goes_to_the_invitations_email():
    send_confirmation(EVENT)
    assert sent_email()["Destination"] == {"ToAddresses": ["jamie@example.com"]}


def test_replies_go_to_reply_to():
    send_confirmation(EVENT)
    assert sent_email()["ReplyToAddresses"] == ["us@example.com"]


def test_an_invitation_without_an_email_gets_nothing():
    confirmation.invitations.get_item.return_value = {"Item": {"email": None}}

    send_confirmation(EVENT)

    mail.ses.send_email.assert_not_called()


def test_a_failed_send_is_logged_instead_of_raised(caplog):
    mail.ses.send_email.side_effect = ClientError({"Error": {}}, "SendEmail")

    send_confirmation(EVENT)

    assert "Failed to send RSVP confirmation for JAMIE234" in caplog.text
