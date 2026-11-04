"""
Update email tests, with mocks in place of SES.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import send_update
from send_update import read_message, recipients, send_all


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    """
    Set the config the Makefile passes in, and mock SES.
    """
    monkeypatch.setattr(send_update, "SITE_URL", "https://example.com")
    monkeypatch.setattr(send_update, "SENDER", "Us <hello@example.com>")
    monkeypatch.setattr(send_update, "REPLY_TO", "us@example.com")
    monkeypatch.setattr(send_update, "ses", MagicMock())
    monkeypatch.setattr(send_update.time, "sleep", lambda _: None)


MESSAGE = {
    "subject": "The itinerary is up",
    "audience": "everyone",
    "link": ("See the itinerary", "/itinerary"),
    "paragraphs": ["We've added the schedule."],
}


def invitation(code="CODE0001", label="Sam", attending=None, **fields):
    """
    A table item for an invitation with one guest.
    """
    return {
        "invite_code": code,
        "label": label,
        "email": "sam@example.com",
        "responded_at": None if attending is None else "2026-11-01T00:00:00+00:00",
        "updates_opt_out": False,
        "guests": [{"name": label, "attending": attending}],
        **fields,
    }


def sent_email():
    """
    The arguments of the one email sent to SES.
    """
    send_update.ses.send_email.assert_called_once()
    return send_update.ses.send_email.call_args.kwargs


# Reading message files


def message_file(tmp_path, text):
    """
    Write a message file and read it back.
    """
    path = tmp_path / "update.txt"
    path.write_text(text, encoding="utf-8")
    return read_message(path)


def test_a_message_has_headers_then_paragraphs(tmp_path):
    message, problems = message_file(
        tmp_path,
        "Subject: Hi\nAudience: everyone\nLink: Go | /itinerary\n\n"
        "One.\nStill one.\n\nTwo.\n",
    )

    assert not problems
    assert message == {
        "subject": "Hi",
        "audience": "everyone",
        "link": ("Go", "/itinerary"),
        "paragraphs": ["One.\nStill one.", "Two."],
    }


def test_a_message_needs_a_subject_and_audience(tmp_path):
    _, problems = message_file(tmp_path, "Heading: Hi\n\nHello.\n")
    assert problems == ["Missing header: Subject", "Missing header: Audience"]


def test_an_unknown_audience_is_a_problem(tmp_path):
    _, problems = message_file(tmp_path, "Subject: Hi\nAudience: friends\n\nHello.\n")
    assert problems == ["Audience should be one of: accepted, no-response, everyone"]


def test_a_misspelled_header_is_a_problem(tmp_path):
    _, problems = message_file(
        tmp_path, "Subject: Hi\nAudience: everyone\nHeadng: Hi\n\nHello.\n"
    )
    assert problems == ["Unknown header: Headng: Hi"]


# Choosing recipients


def test_accepted_is_invitations_with_someone_coming():
    coming = invitation(attending=True)
    not_coming = invitation(attending=False)

    to_send, _ = recipients([coming, not_coming], "accepted", set())

    assert to_send == [coming]


def test_no_response_is_invitations_without_an_rsvp():
    answered = invitation(attending=False)
    unanswered = invitation()

    to_send, _ = recipients([answered, unanswered], "no-response", set())

    assert to_send == [unanswered]


def test_invitations_without_an_email_are_skipped():
    to_send, skipped = recipients([invitation(email=None)], "everyone", set())

    assert not to_send
    assert skipped["without an email"] == 1


def test_opted_out_invitations_are_skipped():
    to_send, skipped = recipients([invitation(updates_opt_out=True)], "everyone", set())

    assert not to_send
    assert skipped["opted out"] == 1


def test_invitations_already_sent_to_are_skipped():
    to_send, skipped = recipients([invitation()], "everyone", {"CODE0001"})

    assert not to_send
    assert skipped["already sent"] == 1


# The email


def test_the_email_greets_the_invitation():
    html = send_update.html(MESSAGE, invitation(label="Sam <Alex>"))
    assert "Hi Sam &lt;Alex&gt;," in html


def test_a_site_link_gets_the_site_address():
    assert send_update.site_url("/itinerary") == "https://example.com/itinerary"


def test_a_full_link_is_left_as_is():
    assert send_update.site_url("https://maps.example") == "https://maps.example"


def test_the_plain_text_email():
    assert send_update.text(MESSAGE, invitation()) == (
        "Hi Sam,\n\n"
        "We've added the schedule.\n\n"
        "See the itinerary: https://example.com/itinerary\n\n"
        "--\nStop getting updates: https://example.com/opt-out?invite_code=CODE0001"
    )


# Sending


def test_an_update_goes_to_the_invitations_email():
    send_update.send(MESSAGE, invitation())
    assert sent_email()["Destination"] == {"ToAddresses": ["sam@example.com"]}


def test_replies_and_bounces_go_to_reply_to():
    send_update.send(MESSAGE, invitation())

    assert sent_email()["ReplyToAddresses"] == ["us@example.com"]
    assert sent_email()["FeedbackForwardingEmailAddress"] == "us@example.com"


def test_the_unsubscribe_header_opens_the_invitations_opt_out_page():
    send_update.send(MESSAGE, invitation())

    headers = sent_email()["Content"]["Simple"]["Headers"]
    assert headers == [
        {
            "Name": "List-Unsubscribe",
            "Value": "<https://example.com/opt-out?invite_code=CODE0001>",
        }
    ]


def test_a_test_send_goes_to_the_given_address_marked_test():
    send_update.send(MESSAGE, invitation(), to="us@example.com")

    assert sent_email()["Destination"] == {"ToAddresses": ["us@example.com"]}
    subject = sent_email()["Content"]["Simple"]["Subject"]["Data"]
    assert subject == "[Test] The itinerary is up"


def test_only_successful_sends_are_recorded(tmp_path):
    send_update.ses.send_email.side_effect = [
        None,
        ClientError({"Error": {"Code": "MessageRejected"}}, "SendEmail"),
    ]
    sent_path = tmp_path / "update.sent.dev.csv"

    send_all(MESSAGE, [invitation("CODE0001"), invitation("CODE0002")], sent_path)

    assert send_update.sent(sent_path) == {"CODE0001"}
