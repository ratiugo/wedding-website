"""
Invitation tests, with mocks in place of the database and S3.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import invitation
from invitation import BadRequest, Invitation


def guest(guest_id, name, plus_one=False, child=False):
    """
    A guest who hasn't responded, as Database.get_invitation returns them.
    """
    return {
        "id": guest_id,
        "name": name,
        "plus_one": plus_one,
        "child": child,
        "attending": None,
        "dietary": "",
    }


INVITATION = {
    "id": 1,
    "invite_code": "TEST01",
    "label": "Morgan, Sam & Ellie",
    "notes": "",
    "responded_at": None,
    "guests": [
        guest(1, "Morgan Rivera"),
        guest(2, "Sam Rivera"),
        guest(3, "Ellie Rivera", child=True),
    ],
}

INVITATION_WITH_PLUS_ONE = {
    "id": 2,
    "invite_code": "TEST02",
    "label": "Jamie",
    "notes": "",
    "responded_at": None,
    "guests": [guest(4, "Jamie Lee"), guest(5, "Plus-one", plus_one=True)],
}


@pytest.fixture(name="database", autouse=True)
def database_fixture(monkeypatch):
    """
    A mock database, which returns INVITATION unless a test says otherwise.
    """
    database = MagicMock()
    database.get_invitation.return_value = INVITATION
    monkeypatch.setattr(invitation, "database", database)
    return database


@pytest.fixture(name="s3", autouse=True)
def s3_fixture(monkeypatch):
    """
    A mock S3 client.
    """
    s3 = MagicMock()
    monkeypatch.setattr(invitation, "s3", s3)
    return s3


def published_event(s3):
    """
    The one event written to S3, decoded.
    """
    s3.put_object.assert_called_once()
    return json.loads(s3.put_object.call_args.kwargs["Body"])


def test_get_looks_up_the_invite_code_ignoring_case_and_spaces(database):
    invite = Invitation.get(" tes t01 ")

    database.get_invitation.assert_called_once_with("TEST01")
    assert invite.view() == {
        "invite_code": "TEST01",
        "label": "Morgan, Sam & Ellie",
        "notes": "",
        "responded_at": None,
        "guests": INVITATION["guests"],
    }


def test_get_unknown_invite_code_returns_none(database):
    database.get_invitation.return_value = None
    assert Invitation.get("ZZZZZZ") is None


@pytest.mark.parametrize("invite_code", ["", "ABC", "TOOLONG1", "AB-C12"])
def test_get_malformed_invite_code_returns_none_without_a_lookup(database, invite_code):
    assert Invitation.get(invite_code) is None
    database.get_invitation.assert_not_called()


def test_first_rsvp_is_saved_and_published(database, s3):
    saved = Invitation.get("TEST01").respond(
        {
            "guests": [
                {"id": 1, "attending": True},
                {"id": 2, "attending": True},
                {"id": 3, "attending": False},
            ],
            "notes": "High chair?",
        }
    )

    database.save_response.assert_called_once_with(
        1,
        [
            {"id": 1, "attending": True, "dietary": "", "plus_one_name": None},
            {"id": 2, "attending": True, "dietary": "", "plus_one_name": None},
            {"id": 3, "attending": False, "dietary": "", "plus_one_name": None},
        ],
        "High chair?",
    )
    assert s3.put_object.call_args.kwargs["Key"].startswith("rsvps/TEST01/")
    event = published_event(s3)
    assert (event["invitation"], event["previous"]) == (saved.view(), None)


def test_updated_rsvp_is_published_with_the_previous_response(database, s3):
    previous = {
        **INVITATION,
        "responded_at": datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc),
    }
    database.get_invitation.side_effect = [previous, INVITATION]

    saved = Invitation.get("TEST01").respond(
        {
            "guests": [
                {"id": 1, "attending": False},
                {"id": 2, "attending": False},
                {"id": 3, "attending": False},
            ]
        }
    )

    event = published_event(s3)
    assert event["invitation"] == saved.view()
    assert event["previous"]["responded_at"] == "2026-10-25T01:00:00+00:00"


def test_text_is_trimmed_and_dietary_dropped_for_guests_not_coming(database):
    Invitation.get("TEST01").respond(
        {
            "guests": [
                {"id": 1, "attending": True, "dietary": " Vegan "},
                {"id": 2, "attending": False, "dietary": "Vegan"},
                {"id": 3, "attending": False},
            ],
            "notes": " hi ",
        }
    )

    saved_answers, notes = database.save_response.call_args.args[1:]
    assert [answer["dietary"] for answer in saved_answers] == ["Vegan", "", ""]
    assert notes == "hi"


def test_body_without_a_guest_list_is_rejected(database):
    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST01").respond([])

    assert str(error.value) == "Expected {'guests': [{'id': ...}, ...]}."
    database.save_response.assert_not_called()


def test_answer_without_a_guest_id_is_rejected(database):
    body = {"guests": [{"attending": True}]}

    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST01").respond(body)

    assert str(error.value) == "Expected {'guests': [{'id': ...}, ...]}."
    database.save_response.assert_not_called()


def test_every_guest_must_be_answered(database):
    body = {"guests": [{"id": 1, "attending": True}, {"id": 2, "attending": True}]}

    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST01").respond(body)

    assert str(error.value) == "Please answer for every guest on the invitation."
    database.save_response.assert_not_called()


def test_answers_for_another_invitations_guests_are_rejected(database):
    body = {"guests": [{"id": 4, "attending": True}, {"id": 5, "attending": True}]}

    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST01").respond(body)

    assert str(error.value) == "Please answer for every guest on the invitation."
    database.save_response.assert_not_called()


def test_attending_must_be_true_or_false(database):
    body = {
        "guests": [
            {"id": 1, "attending": "yes"},
            {"id": 2, "attending": True},
            {"id": 3, "attending": True},
        ]
    }

    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST01").respond(body)

    assert str(error.value) == "Please say whether Morgan Rivera is attending."
    database.save_response.assert_not_called()


def test_plus_one_who_is_coming_needs_a_name(database):
    database.get_invitation.return_value = INVITATION_WITH_PLUS_ONE
    body = {"guests": [{"id": 4, "attending": True}, {"id": 5, "attending": True}]}

    with pytest.raises(BadRequest) as error:
        Invitation.get("TEST02").respond(body)

    assert str(error.value) == "Please tell us your guest's name."
    database.save_response.assert_not_called()


def test_only_the_plus_one_can_be_named(database):
    database.get_invitation.return_value = INVITATION_WITH_PLUS_ONE

    Invitation.get("TEST02").respond(
        {
            "guests": [
                {"id": 4, "attending": True, "name": "Someone else"},
                {"id": 5, "attending": True, "name": " Alex "},
            ]
        }
    )

    saved_answers = database.save_response.call_args.args[1]
    assert [answer["plus_one_name"] for answer in saved_answers] == [None, "Alex"]


def test_rsvp_is_saved_even_if_publishing_fails(database, s3, caplog):
    s3.put_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket"}}, "PutObject"
    )

    Invitation.get("TEST01").respond(
        {
            "guests": [
                {"id": 1, "attending": True},
                {"id": 2, "attending": True},
                {"id": 3, "attending": True},
            ]
        }
    )

    database.save_response.assert_called_once()
    assert "Failed to publish RSVP event for TEST01" in caplog.text
