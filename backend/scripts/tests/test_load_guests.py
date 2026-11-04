"""
Guest list loading tests, with a mock in place of the DynamoDB table.
"""

from unittest.mock import MagicMock

import load_guests
from load_guests import CODE_ALPHABET, add, read_guest_list


def guest_list(tmp_path, text):
    """
    Write a guest list CSV and read it back.
    """
    path = tmp_path / "guests.csv"
    path.write_text(text, encoding="utf-8")
    return read_guest_list(path)


GUESTS = """invitation,email,name,plus_one,child
"Morgan, Sam & Ellie",morgan@example.com,Morgan Rivera,,
"Morgan, Sam & Ellie",,Sam Rivera,,
"Morgan, Sam & Ellie",,Ellie Rivera,,Yes
Jamie,,Jamie Lee,,
Jamie,,Plus-one,yes,
"""


def test_rows_are_grouped_into_invitations(tmp_path):
    invitations, problems = guest_list(tmp_path, GUESTS)

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
        },
        {
            "label": "Jamie",
            "email": "",
            "guests": [
                {"name": "Jamie Lee", "plus_one": False, "child": False},
                {"name": "Plus-one", "plus_one": True, "child": False},
            ],
        },
    ]


def test_problems_are_listed_by_row(tmp_path):
    _, problems = guest_list(
        tmp_path,
        "invitation,email,name,plus_one,child\n"
        "Jamie,jamie@example.com,Jamie Lee,no,\n"
        "Jamie,other@example.com,Plus-one,yes,\n"
        ",,Nobody,,\n"
        "Sam,not-an-email,Sam,,\n",
    )

    assert problems == [
        "Row 2: plus_one should be blank or yes, not no",
        "Row 3: Jamie already has a different email",
        "Row 4: needs an invitation and a name",
        "Row 5: not-an-email isn't an email address",
    ]


def test_a_guest_list_needs_invitation_and_name_columns(tmp_path):
    assert guest_list(tmp_path, "label,guest\nJamie,Jamie Lee\n") == (
        [],
        ["Missing column(s): invitation, name"],
    )


def test_invitations_are_added_with_new_codes_without_overwriting(tmp_path):
    invitations, _ = guest_list(tmp_path, GUESTS)
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
    assert items[0]["email"] == "morgan@example.com"
    assert items[1]["email"] is None
    assert items[1]["guests"][1] == {
        "id": 2,
        "name": "Plus-one",
        "plus_one": True,
        "child": False,
        "attending": None,
        "dietary": "",
    }


def test_new_codes_avoid_taken_ones(monkeypatch):
    picks = iter("AAAAAAAA" + "BBBBBBBB")
    monkeypatch.setattr(load_guests.secrets, "choice", lambda _: next(picks))

    assert load_guests.new_code({"AAAAAAAA"}) == "BBBBBBBB"
