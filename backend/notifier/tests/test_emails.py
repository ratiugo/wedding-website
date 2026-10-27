"""
RSVP email tests: the subject, body and what's sent to SES.
"""

from unittest.mock import MagicMock

import emails
from emails import RsvpEmail


def guest(name, attending, **fields):
    """
    A guest as it appears in an RSVP event.
    """
    return {
        "id": 1,
        "name": name,
        "plus_one": False,
        "child": False,
        "attending": attending,
        "dietary": "",
        **fields,
    }


def invitation(guests, notes="", responded_at="2026-10-25T01:00:00+00:00"):
    """
    An invitation for a sample invite code, as it appears in an RSVP event.
    """
    return {
        "invite_code": "JAMIE2",
        "label": "Jamie",
        "notes": notes,
        "responded_at": responded_at,
        "guests": guests,
    }


def test_first_rsvp():
    email = RsvpEmail(
        {
            "invitation": invitation(
                [guest("Jamie", True), guest("Plus-one", False, plus_one=True)]
            ),
            "previous": None,
        }
    )

    assert email.subject() == "Jamie just RSVP'd! (1 of 2 coming)"
    assert email.body() == "\n".join(
        [
            "Jamie just RSVP'd!",
            "",
            "Coming (1)",
            "  • Jamie",
            "",
            "Not coming (1)",
            "  • Plus-one",
            "",
            "Invite code: JAMIE2",
            "Responded: Sat Oct 24, 2026 at 6:00 PM PDT",
        ]
    )


def test_first_rsvp_with_nobody_coming_sends_regrets():
    email = RsvpEmail(
        {"invitation": invitation([guest("Jamie", False)]), "previous": None}
    )
    assert email.subject() == "Jamie just RSVP'd (sending their regrets)"


def test_updated_rsvp_lists_what_changed():
    email = RsvpEmail(
        {
            "previous": invitation(
                [guest("Jamie", True), guest("Plus-one", False, plus_one=True)]
            ),
            "invitation": invitation(
                [
                    guest("Jamie", True),
                    guest("Alex", True, plus_one=True, child=True, dietary="Vegan"),
                ],
                notes="Bringing Alex!",
            ),
        }
    )

    assert email.subject() == "Jamie updated their RSVP (2 of 2 coming)"
    assert email.body().startswith(
        "\n".join(
            [
                "Jamie updated their RSVP.",
                "",
                "What changed",
                "  • Plus-one is now Alex",
                "  • Alex is now coming",
                "  • Alex's dietary: none → Vegan",
                "  • Note: none → Bringing Alex!",
                "",
                "Coming (2)",
                "  • Jamie",
                "  • Alex (child, dietary: Vegan)",
                "",
                "Their note:",
                "  Bringing Alex!",
            ]
        )
    )


def test_guest_who_can_no_longer_come_is_a_change():
    email = RsvpEmail(
        {
            "previous": invitation([guest("Jamie", True)]),
            "invitation": invitation([guest("Jamie", False)]),
        }
    )
    assert email.changes() == ["Jamie can no longer come"]


def test_resubmitting_the_same_answers_sends_no_email(monkeypatch):
    monkeypatch.setattr(emails, "ses", MagicMock())
    answers = invitation([guest("Jamie", True)])

    RsvpEmail({"previous": answers, "invitation": answers}).send()

    emails.ses.send_email.assert_not_called()


def test_send_emails_every_recipient_as_plain_text(monkeypatch):
    monkeypatch.setattr(emails, "ses", MagicMock())
    email = RsvpEmail(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    )

    email.send()

    emails.ses.send_email.assert_called_once_with(
        FromEmailAddress="rsvp@example.com",
        Destination={"ToAddresses": ["colton@example.com", "tess@example.com"]},
        Content={
            "Simple": {
                "Subject": {"Data": email.subject(), "Charset": "UTF-8"},
                "Body": {"Text": {"Data": email.body(), "Charset": "UTF-8"}},
            }
        },
    )
