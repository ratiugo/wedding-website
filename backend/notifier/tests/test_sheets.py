"""
Guests worksheet tests.
"""

from unittest.mock import MagicMock

import pytest

import sheets
from sheets import GuestSheet

EVENT = {
    "invitation": {
        "invite_code": "SHAHPD",
        "label": "Priya & Dev",
        "notes": "Can't wait!",
        "responded_at": "2026-10-25T01:00:00+00:00",
        "guests": [
            {
                "name": "Priya Shah",
                "attending": True,
                "child": False,
                "plus_one": False,
                "dietary": "Vegan",
            },
            {
                "name": "Dev Shah",
                "attending": False,
                "child": False,
                "plus_one": True,
                "dietary": "",
            },
        ],
    }
}

ROWS = [
    [
        "Priya & Dev",
        "SHAHPD",
        "Priya Shah",
        "Coming",
        "No",
        "No",
        "Vegan",
        "Can't wait!",
        "2026-10-24 18:00",
    ],
    [
        "Priya & Dev",
        "SHAHPD",
        "Dev Shah",
        "Not coming",
        "No",
        "Yes",
        "",
        "Can't wait!",
        "2026-10-24 18:00",
    ],
]


@pytest.fixture(name="worksheet")
def worksheet_fixture(monkeypatch):
    """
    A mock Guests worksheet.
    """
    client = MagicMock()
    monkeypatch.setattr(sheets.gspread, "service_account_from_dict", lambda key: client)
    return client.open_by_key.return_value.worksheet.return_value


def test_first_rsvp_appends_a_row_per_guest(worksheet):
    worksheet.col_values.return_value = ["Invite code", "RIVERA"]

    GuestSheet("sheet-id", {}).apply(EVENT)

    worksheet.append_rows.assert_called_once_with(ROWS)
    worksheet.update.assert_not_called()


def test_updated_rsvp_overwrites_that_invitations_rows(worksheet):
    worksheet.col_values.return_value = [
        "Invite code",
        "RIVERA",
        "SHAHPD",
        "SHAHPD",
        "JAMIE2",
    ]

    GuestSheet("sheet-id", {}).apply(EVENT)

    worksheet.update.assert_called_once_with(values=ROWS, range_name="A3:I4")
    worksheet.append_rows.assert_not_called()
