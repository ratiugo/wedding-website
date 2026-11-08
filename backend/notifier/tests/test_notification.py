"""
RSVP notification tests: the subject, body, HTML and what's sent to SES.
"""

from unittest.mock import MagicMock

import mail
from notification import RsvpNotification


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
    email = RsvpNotification(
        {
            "invitation": invitation(
                [
                    guest("Jamie", True, events={"bbq": True, "brunch": False}),
                    guest("Plus-one", False, plus_one=True),
                ]
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
            "Friday BBQ (1)",
            "  • Jamie",
            "",
            "Sunday brunch (0)",
            "",
            "Not coming (1)",
            "  • Plus-one",
            "",
            "Invite code: JAMIE2",
            "Responded: Sat Oct 24, 2026 at 6:00 PM PDT",
        ]
    )


def test_first_rsvp_with_nobody_coming_sends_regrets():
    email = RsvpNotification(
        {"invitation": invitation([guest("Jamie", False)]), "previous": None}
    )
    assert email.subject() == "Jamie just RSVP'd (sending their regrets)"


def test_updated_rsvp_lists_what_changed():
    email = RsvpNotification(
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
                "Friday BBQ (0)",
                "",
                "Sunday brunch (0)",
                "",
                "Their note:",
                "  Bringing Alex!",
            ]
        )
    )


def test_guest_who_can_no_longer_come_is_a_change():
    email = RsvpNotification(
        {
            "previous": invitation([guest("Jamie", True)]),
            "invitation": invitation([guest("Jamie", False)]),
        }
    )
    assert email.changes() == ["Jamie can no longer come"]


def test_a_changed_event_answer_is_a_change():
    email = RsvpNotification(
        {
            "previous": invitation([guest("Jamie", True, events={"bbq": False})]),
            "invitation": invitation([guest("Jamie", True, events={"bbq": True})]),
        }
    )
    assert email.changes() == ["Jamie's Friday BBQ: not coming → coming"]


def test_resubmitting_the_same_answers_has_no_changes():
    answers = invitation([guest("Jamie", True)])
    email = RsvpNotification({"previous": answers, "invitation": answers})
    assert not email.changes()


def test_html_shows_whether_its_new_and_how_many_are_coming():
    html = RsvpNotification(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    ).html()

    assert "New RSVP" in html
    assert "1 of 1 coming" in html


def test_a_link_in_a_guests_note_isnt_a_real_link():
    note = '<a href="https://spam.example">Click me</a>'
    html = RsvpNotification(
        {"invitation": invitation([guest("Jamie", True)], notes=note), "previous": None}
    ).html()

    assert note not in html


def test_it_goes_to_every_recipient(monkeypatch):
    monkeypatch.setattr(mail, "ses", MagicMock())

    RsvpNotification(
        {"invitation": invitation([guest("Jamie", True)]), "previous": None}
    ).send()

    sent = mail.ses.send_email.call_args.kwargs
    assert sent["FromEmailAddress"] == "Wedding RSVPs <rsvp@example.com>"
    assert sent["Destination"] == {
        "ToAddresses": ["colton@example.com", "tess@example.com"]
    }
