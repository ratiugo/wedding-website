"""
Guest loading tests, with mocks in place of the DynamoDB table and the sheet.
"""

from unittest.mock import MagicMock

import load_guests
from load_guests import CODE_ALPHABET, add, read_invite_list, write_codes

HEADER = ["Invitation", "Guests", "Children", "Plus one", "Plus one name", "Email"]


def invite_list(*rows, header=None):
    """
    Read Invite list rows, given as lists in HEADER's column order.
    """
    return read_invite_list(header or HEADER, [list(row) for row in rows])


def test_a_row_is_an_invitation():
    invitations, problems = invite_list(
        [
            "Morgan, Sam & Ellie",
            "Morgan Rivera, Sam Rivera, Ellie Rivera",
            "Ellie Rivera",
            "No",
            "",
            "morgan@example.com",
        ]
    )

    assert not problems
    assert invitations == [
        {
            "label": "Morgan, Sam & Ellie",
            "email": "morgan@example.com",
            "guests": [
                {"name": "Morgan Rivera", "plus_one": False, "child": False},
                {"name": "Sam Rivera", "plus_one": False, "child": False},
                {"name": "Ellie Rivera", "plus_one": False, "child": True},
            ],
            "row": 2,
        }
    ]


def test_a_plus_one_is_added_as_a_guest():
    invitations, _ = invite_list(["Jamie", "Jamie Lee", "", "Yes", "", ""])
    assert invitations[0]["guests"][1] == {
        "name": "Plus-one",
        "plus_one": True,
        "child": False,
    }


def test_a_known_plus_one_keeps_their_name():
    invitations, _ = invite_list(["Jamie", "Jamie Lee", "", "Yes", "Alex Kim", ""])
    assert invitations[0]["guests"][1]["name"] == "Alex Kim"


def test_rows_without_an_invitation_are_skipped():
    invitations, _ = read_invite_list(
        ["Invitation", "Guests", "Notes"],
        [["Tess & Colton", "Tess, Colton", "Us, no invitation"], ["", "", ""]],
    )
    assert not invitations


def test_problems_are_listed_by_row():
    _, problems = invite_list(
        ["Jamie", "", "", "", "", ""],
        ["Sam", "Sam Lee", "Ellie", "Maybe", "", "not-an-email"],
        ["Sam", "Sam Lee", "", "", "", ""],
    )

    assert problems == [
        "Row 2: needs Guests",
        "Row 3: Ellie in Children isn't one of the Guests",
        "Row 3: Plus one should be Yes, No or blank, not maybe",
        "Row 3: not-an-email isn't an email address",
        "Sam is in the list more than once",
    ]


def test_the_invite_list_needs_invitation_and_guests_columns():
    assert invite_list(["Jamie"], header=["Name"]) == (
        [],
        ["Missing column(s): Guests, Invitation"],
    )


def test_invitations_are_added_with_new_codes_without_overwriting():
    invitations, _ = invite_list(
        ["Jamie", "Jamie Lee", "", "Yes", "", ""],
        ["Sam", "Sam Lee", "", "", "", "sam@example.com"],
    )
    table = MagicMock()

    items = add(table, invitations, {"TAKEN123"})

    added = [call.kwargs for call in table.put_item.call_args_list]
    assert [kwargs["Item"] for kwargs in added] == items
    codes = [item["invite_code"] for item in items]
    assert len(set(codes)) == 2 and "TAKEN123" not in codes
    assert all(len(code) == 8 and set(code) <= set(CODE_ALPHABET) for code in codes)
    assert {kwargs["ConditionExpression"] for kwargs in added} == {
        "attribute_not_exists(invite_code)"
    }
    assert items[0]["email"] is None
    assert items[1]["email"] == "sam@example.com"


def test_new_codes_avoid_taken_ones(monkeypatch):
    picks = iter("AAAAAAAA" + "BBBBBBBB")
    monkeypatch.setattr(load_guests.secrets, "choice", lambda _: next(picks))

    assert load_guests.new_code({"AAAAAAAA"}) == "BBBBBBBB"


def test_codes_are_written_to_each_invitations_row():
    worksheet = MagicMock()
    invitations = [{"label": "Jamie", "row": 5}]
    items = [{"label": "Jamie", "invite_code": "H7KM3QPX"}]

    write_codes(worksheet, ["Invitation", "Guests", "Invite code"], invitations, items)

    worksheet.batch_update.assert_called_once_with(
        [{"range": "C5", "values": [["H7KM-3QPX"]]}]
    )
