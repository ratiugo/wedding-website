"""
Guest loading tests, with mocks in place of the DynamoDB table and the sheet.
"""

from unittest.mock import MagicMock

import load_guests
from load_guests import (
    CODE_ALPHABET,
    add,
    make_plan,
    new_item,
    read_invite_list,
    update,
    write_codes,
)

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
            "code": "",
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
    matched = [({"label": "Jamie", "row": 5}, {"invite_code": "H7KM3QPX"})]

    write_codes(worksheet, ["Invitation", "Guests", "Invite code"], matched)

    worksheet.batch_update.assert_called_once_with(
        [{"range": "C5", "values": [["H7KM-3QPX"]]}]
    )


# Planning


def row(label="Jamie", guests=("Jamie Lee",), email="", code="", children=()):
    """
    An invitation as read from the Invite list.
    """
    return {
        "label": label,
        "email": email,
        "guests": [
            {"name": name, "plus_one": False, "child": name in children}
            for name in guests
        ],
        "row": 2,
        "code": code,
    }


def item(invitation, code="JAMIE234", responded_at=None):
    """
    The table item for an invitation, as if loaded before.
    """
    return {**new_item(invitation, code), "responded_at": responded_at}


def test_a_row_without_a_code_is_new():
    plan = make_plan([row()], [])
    assert plan["new"] == [row()]


def test_a_row_is_matched_by_its_code():
    loaded = item(row())
    plan = make_plan([row(code="JAMIE234")], [loaded])
    assert plan["matched"] == [(row(code="JAMIE234"), loaded)]
    assert not plan["new"] and not plan["changes"]


def test_a_row_without_a_code_is_matched_by_name_instead_of_added_twice():
    plan = make_plan([row()], [item(row())])
    assert not plan["new"]


def test_a_changed_email_is_updated():
    plan = make_plan([row(code="JAMIE234", email="new@example.com")], [item(row())])
    assert plan["changes"][0][1] == {"email": "new@example.com"}


def test_a_rename_is_updated():
    plan = make_plan([row(label="Jamie Lee", code="JAMIE234")], [item(row())])
    assert plan["changes"][0][1] == {"label": "Jamie Lee"}


def test_guests_are_updated_before_they_rsvp():
    changed = row(
        guests=("Jamie Lee", "Finn Lee"), children=("Finn Lee",), code="JAMIE234"
    )
    plan = make_plan([changed], [item(row())])
    assert plan["changes"][0][1]["guests"][1]["child"] is True


def test_guests_are_left_alone_after_they_rsvp():
    changed = row(guests=("Jamie Lee", "Finn Lee"), code="JAMIE234")
    plan = make_plan([changed], [item(row(), responded_at="2026-11-01T00:00:00+00:00")])

    assert not plan["changes"]
    assert plan["warnings"][0].startswith(
        "Jamie has RSVP'd, so its guests weren't changed"
    )


def test_a_plus_ones_name_from_their_rsvp_isnt_a_change():
    invitation = {**row(code="JAMIE234")}
    invitation["guests"] = [
        {"name": "Jamie Lee", "plus_one": False, "child": False},
        {"name": "Plus-one", "plus_one": True, "child": False},
    ]
    loaded = item(invitation)
    loaded["guests"][1]["name"] = "Alex Kim"

    assert not make_plan([invitation], [loaded])["changes"]


def test_an_invitation_missing_from_the_list_is_left_alone():
    plan = make_plan([], [item(row())])
    assert plan["warnings"] == [
        "Jamie (JAMI-E234) isn't in the Invite list, so it's left as is"
    ]


def test_a_code_that_isnt_in_the_table_is_a_problem():
    plan = make_plan([row(code="ZZZZ2222")], [])
    assert plan["problems"] == ["Row 2: ZZZZ-2222 isn't in the table"]


def test_an_update_sets_only_the_changed_fields():
    table = MagicMock()

    update(table, {"invite_code": "JAMIE234"}, {"email": "new@example.com"})

    table.update_item.assert_called_once_with(
        Key={"invite_code": "JAMIE234"},
        UpdateExpression="SET #email = :email",
        ExpressionAttributeNames={"#email": "email"},
        ExpressionAttributeValues={":email": "new@example.com"},
    )
