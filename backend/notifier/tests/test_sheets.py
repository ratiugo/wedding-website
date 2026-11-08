"""
Invite list tests: filling in an invitation's RSVP columns, with a mock worksheet.
"""

from unittest.mock import MagicMock

import pytest

import sheets
from sheets import InviteListSheet, rsvp_values

INVITATION = {
    "invite_code": "SHAHPDXY",
    "label": "Priya & Dev",
    "notes": "Can't wait!",
    "responded_at": "2026-10-25T01:00:00+00:00",
    "guests": [
        {
            "name": "Priya Shah",
            "attending": True,
            "events": {"bbq": True, "brunch": False},
            "child": False,
            "dietary": "Vegan",
        },
        {"name": "Ava Shah", "attending": True, "child": True, "dietary": ""},
        {"name": "Dev Shah", "attending": False, "child": False, "dietary": ""},
    ],
}

HEADER = [
    "Invitation",
    "Guests",
    "",
    "Invite code",
    "Responded",
    "Coming",
    "Not coming",
    "Adults coming",
    "Children coming",
    "Friday BBQ",
    "Sunday brunch",
    "Dietary",
    "RSVP note",
]


@pytest.fixture(name="worksheet")
def worksheet_fixture(monkeypatch):
    """
    A mock Invite list with HEADER, and Priya & Dev's code in row 3.
    """
    client = MagicMock()
    monkeypatch.setattr(sheets.gspread, "service_account_from_dict", lambda key: client)
    worksheet = client.open_by_key.return_value.worksheet.return_value
    worksheet.row_values.return_value = HEADER
    worksheet.col_values.return_value = ["Invite code", "RIVE-RAXY", "SHAH-PDXY"]
    return worksheet


def test_rsvp_values():
    assert rsvp_values(INVITATION) == {
        "Responded": "2026-10-24 18:00",
        "Coming": "Priya Shah, Ava Shah",
        "Not coming": "Dev Shah",
        "Adults coming": 1,
        "Children coming": 1,
        "Friday BBQ": 1,
        "Sunday brunch": 0,
        "Dietary": "Priya Shah: Vegan",
        "RSVP note": "Can't wait!",
    }


def test_the_rsvp_fills_in_its_invitations_row(worksheet):
    InviteListSheet("sheet-id", {}).apply({"invitation": INVITATION})

    cells = worksheet.batch_update.call_args.args[0]
    assert cells[0] == {"range": "E3", "values": [["2026-10-24 18:00"]]}
    assert cells[-1] == {"range": "M3", "values": [["Can't wait!"]]}


def test_an_invite_code_without_a_row_is_skipped(worksheet, caplog):
    worksheet.col_values.return_value = ["Invite code", "RIVE-RAXY"]

    InviteListSheet("sheet-id", {}).apply({"invitation": INVITATION})

    worksheet.batch_update.assert_not_called()
    assert "No row in the Invite list has invite code SHAHPDXY" in caplog.text


def test_missing_columns_are_an_error(worksheet):
    worksheet.row_values.return_value = ["Invitation", "Guests", "Invite code"]

    with pytest.raises(ValueError, match="run make sheet-setup"):
        InviteListSheet("sheet-id", {}).apply({"invitation": INVITATION})
