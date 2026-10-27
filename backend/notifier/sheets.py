"""
Updates the 'Guests' worksheet (initialized in scripts/setup_sheet.py) as RSVP
events happen.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import gspread

TIMEZONE = ZoneInfo("America/Vancouver")

HEADER = [
    "Invitation",
    "Invite code",
    "Guest",
    "Status",
    "Child",
    "Plus-one",
    "Dietary",
    "Note",
    "Updated",
]


class GuestSheet:
    """
    Writes RSVPs to the spreadsheet's Guests worksheet, signed in as the Google
    service account the spreadsheet is shared with.
    """

    def __init__(self, spreadsheet_id, service_account_key):
        """
        Open a spreadsheet's Guests worksheet, given the service account's key (a dict).
        """
        client = gspread.service_account_from_dict(service_account_key)
        self.worksheet = client.open_by_key(spreadsheet_id).worksheet("Guests")

    def apply(self, event):
        """
        Write an RSVP event's guests to the worksheet, one row per guest.

        If the invite code is already in the worksheet (they've responded before), its
        rows are overwritten in place; an invitation's guests never change, so it's the
        same number of rows. Otherwise the rows are appended.
        """
        rows = self.guest_rows(event)
        existing_invite_codes = self.worksheet.col_values(
            HEADER.index("Invite code") + 1
        )

        invite_code = event["invitation"]["invite_code"]
        invitation_row_numbers = [
            row_number
            for row_number, existing in enumerate(existing_invite_codes, start=1)
            if existing == invite_code
        ]
        if invitation_row_numbers:
            first = f"A{invitation_row_numbers[0]}"
            last = gspread.utils.rowcol_to_a1(invitation_row_numbers[-1], len(HEADER))
            self.worksheet.update(values=rows, range_name=f"{first}:{last}")
        else:
            self.worksheet.append_rows(rows)

    def guest_rows(self, event):
        """
        Return one row per guest on the invitation, in HEADER's column order.
        """
        invitation = event["invitation"]
        responded = datetime.fromisoformat(invitation["responded_at"])
        return [
            [
                invitation["label"],
                invitation["invite_code"],
                guest["name"],
                "Coming" if guest["attending"] else "Not coming",
                "Yes" if guest["child"] else "No",
                "Yes" if guest["plus_one"] else "No",
                guest["dietary"],
                invitation["notes"],
                f"{responded.astimezone(TIMEZONE):%Y-%m-%d %H:%M}",
            ]
            for guest in invitation["guests"]
        ]
