"""
Update email tests, with mocks in place of SES.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import mail
import send_update
from send_update import (
    confirm_send,
    get_recipients,
    parse_message,
    sample_invitation,
    send_to_recipients,
    validate_message,
)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    """
    Set the config the Makefile passes in, and mock SES.
    """
    monkeypatch.setattr(send_update, "SITE_URL", "https://example.com")
    monkeypatch.setattr(send_update, "SENDER", "Us <hello@example.com>")
    monkeypatch.setattr(send_update, "REPLY_TO", "us@example.com")
    monkeypatch.setattr(mail, "ses", MagicMock())
    monkeypatch.setattr(send_update.time, "sleep", lambda _: None)


MESSAGE = {
    "name": "itinerary",
    "subject": "The itinerary is up",
    "audience": "everyone",
    "links": [("See the itinerary", "/itinerary")],
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
    mail.ses.send_email.assert_called_once()
    return mail.ses.send_email.call_args.kwargs


# Parsing message files


def test_a_message_file_is_headers_then_paragraphs(tmp_path):
    path = tmp_path / "update.txt"
    path.write_text(
        "Subject: Hi\nAudience: everyone\nLink: Go | /itinerary\nLink: Map | /map\n\n"
        "One.\nStill one.\n\nTwo.\n",
        encoding="utf-8",
    )

    assert parse_message(path) == {
        "name": "update",
        "subject": "Hi",
        "audience": "everyone",
        "links": [("Go", "/itinerary"), ("Map", "/map")],
        "paragraphs": ["One.\nStill one.", "Two."],
    }


# Validating messages


def test_a_complete_message_is_valid():
    assert not validate_message(MESSAGE)


def test_a_message_needs_a_subject_and_audience():
    errors = validate_message({"name": "update", "paragraphs": ["Hello."], "links": []})
    assert errors == ["Missing header: Subject", "Missing header: Audience"]


def test_an_unknown_audience_is_an_error():
    errors = validate_message({**MESSAGE, "audience": "friends"})
    assert errors == ["Audience should be one of: accepted, no-response, everyone"]


def test_a_misspelled_header_is_an_error():
    errors = validate_message({**MESSAGE, "headng": "Hi"})
    assert errors == ["Unknown header: headng"]


def test_a_link_needs_text_and_a_url():
    errors = validate_message({**MESSAGE, "links": [("", "/itinerary")]})
    assert errors == ["Link should be like: See the itinerary | /itinerary"]


def test_a_message_needs_a_body():
    errors = validate_message({**MESSAGE, "paragraphs": []})
    assert errors == ["The message is empty"]


# Choosing recipients


def test_accepted_is_invitations_with_someone_coming():
    coming = invitation(attending=True)
    not_coming = invitation(attending=False)

    to_send, _ = get_recipients(
        [coming, not_coming], {**MESSAGE, "audience": "accepted"}
    )

    assert to_send == [coming]


def test_no_response_is_invitations_without_an_rsvp():
    answered = invitation(attending=False)
    unanswered = invitation()

    to_send, _ = get_recipients(
        [answered, unanswered], {**MESSAGE, "audience": "no-response"}
    )

    assert to_send == [unanswered]


def test_invitations_without_an_email_are_skipped():
    to_send, skipped = get_recipients([invitation(email=None)], MESSAGE)

    assert not to_send
    assert skipped["no email"] == 1


def test_opted_out_invitations_are_skipped():
    to_send, skipped = get_recipients([invitation(updates_opt_out=True)], MESSAGE)

    assert not to_send
    assert skipped["opted out"] == 1


def test_invitations_already_sent_to_are_skipped():
    to_send, skipped = get_recipients([invitation(updates_sent={"itinerary"})], MESSAGE)

    assert not to_send
    assert skipped["already sent"] == 1


def test_the_sample_is_the_first_recipient():
    recipients = [invitation(label="Ana"), invitation(label="Ben")]
    assert sample_invitation(recipients, MESSAGE, recipients) == recipients[0]


def test_the_sample_is_from_the_audience_when_everyone_already_has_it():
    sent = invitation(updates_sent={"itinerary"})
    assert sample_invitation([sent], MESSAGE, []) == sent


# Confirming


def test_yes_sends_nothing_when_nobody_is_left(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert not confirm_send(MESSAGE, invitation(), can_send=False)


def test_test_sends_a_copy_to_reply_to(monkeypatch):
    answers = iter(["test", "stop"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    confirm_send(MESSAGE, invitation(), can_send=False)

    assert sent_email()["Destination"] == {"ToAddresses": ["us@example.com"]}


# The email


def test_the_email_greets_the_invitation():
    html = send_update.render_html(MESSAGE, invitation(label="Sam <Alex>"))
    assert "Hi Sam &lt;Alex&gt;," in html


def test_the_email_uses_the_photo_from_the_site():
    html = send_update.render_html(MESSAGE, invitation())
    assert "https://example.com/images/email.jpg" in html


def test_a_site_link_gets_the_site_address():
    assert send_update.full_url("/itinerary") == "https://example.com/itinerary"


def test_a_full_link_is_left_as_is():
    assert send_update.full_url("https://maps.example") == "https://maps.example"


def test_the_plain_text_email():
    assert send_update.render_text(MESSAGE, invitation()) == (
        "Hi Sam,\n\n"
        "We've added the schedule.\n\n"
        "See the itinerary: https://example.com/itinerary\n\n"
        "--\nStop getting updates: https://example.com/opt-out?invite_code=CODE0001"
    )


# Sending


def test_an_update_goes_to_the_invitations_email():
    send_update.send_email(MESSAGE, invitation())
    assert sent_email()["Destination"] == {"ToAddresses": ["sam@example.com"]}


def test_replies_and_bounces_go_to_reply_to():
    send_update.send_email(MESSAGE, invitation())

    assert sent_email()["ReplyToAddresses"] == ["us@example.com"]
    assert sent_email()["FeedbackForwardingEmailAddress"] == "us@example.com"


def test_the_unsubscribe_header_opens_the_invitations_opt_out_page():
    send_update.send_email(MESSAGE, invitation())

    headers = sent_email()["Content"]["Simple"]["Headers"]
    assert headers == [
        {
            "Name": "List-Unsubscribe",
            "Value": "<https://example.com/opt-out?invite_code=CODE0001>",
        }
    ]


def test_a_test_send_goes_to_the_given_address_marked_test():
    send_update.send_email(MESSAGE, invitation(), to="us@example.com")

    assert sent_email()["Destination"] == {"ToAddresses": ["us@example.com"]}
    subject = sent_email()["Content"]["Simple"]["Subject"]["Data"]
    assert subject == "[Test] The itinerary is up"


def test_only_successful_sends_are_recorded_on_the_invitation():
    mail.ses.send_email.side_effect = [
        None,
        ClientError({"Error": {"Code": "MessageRejected"}}, "SendEmail"),
    ]
    table = MagicMock()

    send_to_recipients(table, MESSAGE, [invitation("CODE0001"), invitation("CODE0002")])

    table.update_item.assert_called_once_with(
        Key={"invite_code": "CODE0001"},
        UpdateExpression="ADD updates_sent :name",
        ExpressionAttributeValues={":name": {"itinerary"}},
    )
