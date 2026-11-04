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
    The site and addresses the Makefile passes in, and a mock SES client.
    """
    monkeypatch.setattr(send_update, "SITE_URL", "https://example.com")
    monkeypatch.setattr(send_update, "SENDER", "Us <hello@example.com>")
    monkeypatch.setattr(send_update, "REPLY_TO", "us@example.com")
    monkeypatch.setattr(send_update, "ses", MagicMock())
    monkeypatch.setattr(send_update.time, "sleep", lambda _: None)


def message_file(tmp_path, text):
    """
    Write a message file and read it back.
    """
    path = tmp_path / "update.txt"
    path.write_text(text, encoding="utf-8")
    return read_message(path)


MESSAGE = """Subject: The itinerary is up
Audience: accepted
Heading: The weekend
Link: See the itinerary | /itinerary

We've added the schedule.
Friday has welcome drinks.

See you soon!
"""


def invitation(code, label, email="a@example.com", attending=None, **fields):
    """
    A table item for an invitation with one guest.
    """
    return {
        "invite_code": code,
        "label": label,
        "email": email,
        "responded_at": None if attending is None else "2026-11-01T00:00:00+00:00",
        "updates_opt_out": False,
        "guests": [{"name": label, "attending": attending}],
        **fields,
    }


def test_a_message_has_headers_then_paragraphs(tmp_path):
    assert message_file(tmp_path, MESSAGE) == (
        {
            "subject": "The itinerary is up",
            "audience": "accepted",
            "heading": "The weekend",
            "link": ("See the itinerary", "/itinerary"),
            "paragraphs": [
                "We've added the schedule.\nFriday has welcome drinks.",
                "See you soon!",
            ],
        },
        [],
    )


def test_message_problems_are_listed(tmp_path):
    _, problems = message_file(
        tmp_path, "Subjet: Hi\nAudience: friends\nLink: /itinerary\n\n"
    )

    assert problems == [
        "Unknown header: Subjet: Hi",
        "Missing header: Subject",
        "Audience should be one of: accepted, no-response, everyone",
        "Link should be like: See the itinerary | /itinerary",
        "The message is empty",
    ]


def test_recipients_are_the_audience_minus_who_cant_or_already_got_it():
    items = [
        invitation("CODE0001", "Coming", attending=True),
        invitation("CODE0002", "Not coming", attending=False),
        invitation("CODE0003", "No answer"),
        invitation("CODE0004", "No email", email=None, attending=True),
        invitation("CODE0005", "Opted out", attending=True, updates_opt_out=True),
        invitation("CODE0006", "Already sent", attending=True),
    ]

    to_send, skipped = recipients(items, "accepted", {"CODE0006"})

    assert [item["label"] for item in to_send] == ["Coming"]
    assert skipped == {"without an email": 1, "opted out": 1, "already sent": 1}
    assert [item["label"] for item in recipients(items, "no-response", set())[0]] == [
        "No answer"
    ]
    assert len(recipients(items, "everyone", set())[0]) == 4


def test_the_email_greets_the_invitation_and_links_to_its_opt_out(tmp_path):
    message, _ = message_file(tmp_path, MESSAGE)
    item = invitation("CODE0001", "Sam & <Alex>")

    html = send_update.html(message, item)
    text = send_update.text(message, item)

    assert "Sam <span" in html and "&lt;Alex&gt;" in html and "<Alex>" not in html
    assert "The weekend" in html
    assert "added the schedule.<br>Friday" in html
    assert 'href="https://example.com/itinerary"' in html
    assert 'href="https://example.com/opt-out?invite_code=CODE0001"' in html
    assert text == (
        "Hi Sam & <Alex>,\n\n"
        "We've added the schedule.\nFriday has welcome drinks.\n\n"
        "See you soon!\n\n"
        "See the itinerary: https://example.com/itinerary\n\n"
        "--\nStop getting updates: https://example.com/opt-out?invite_code=CODE0001"
    )


def test_send_sets_reply_to_bounces_and_the_unsubscribe_header(tmp_path):
    message, _ = message_file(tmp_path, MESSAGE)

    send_update.send(message, invitation("CODE0001", "Sam", email="sam@example.com"))

    kwargs = send_update.ses.send_email.call_args.kwargs
    assert kwargs["FromEmailAddress"] == "Us <hello@example.com>"
    assert kwargs["Destination"] == {"ToAddresses": ["sam@example.com"]}
    assert kwargs["ReplyToAddresses"] == ["us@example.com"]
    assert kwargs["FeedbackForwardingEmailAddress"] == "us@example.com"
    simple = kwargs["Content"]["Simple"]
    assert simple["Subject"]["Data"] == "The itinerary is up"
    assert simple["Headers"] == [
        {
            "Name": "List-Unsubscribe",
            "Value": "<https://example.com/opt-out?invite_code=CODE0001>",
        }
    ]


def test_a_test_send_goes_only_to_the_given_address(tmp_path):
    message, _ = message_file(tmp_path, MESSAGE)

    send_update.send(message, invitation("CODE0001", "Sam"), to="us@example.com")

    kwargs = send_update.ses.send_email.call_args.kwargs
    assert kwargs["Destination"] == {"ToAddresses": ["us@example.com"]}
    assert (
        kwargs["Content"]["Simple"]["Subject"]["Data"] == "[Test] The itinerary is up"
    )


def test_only_successful_sends_are_recorded(tmp_path):
    message, _ = message_file(tmp_path, MESSAGE)
    items = [invitation("CODE0001", "Sam"), invitation("CODE0002", "Alex")]
    send_update.ses.send_email.side_effect = [
        None,
        ClientError({"Error": {"Code": "MessageRejected"}}, "SendEmail"),
    ]
    sent_path = tmp_path / "update.sent.dev.csv"

    failed = send_all(message, items, sent_path)

    assert len(failed) == 1 and failed[0].startswith("Alex <a@example.com>")
    assert send_update.sent(sent_path) == {"CODE0001"}
