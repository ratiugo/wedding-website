"""
Fills in each invitation's RSVP columns on the planning workbook's Invite list (see
shared/invite_list.py), as RSVP events happen.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread

from events import EVENTS, coming_to
from invite_list import (
    INVITE_CODE,
    RSVP_COLUMNS,
    INVITE_LIST_WORKSHEET,
    column_numbers,
    plain_code,
)

TIMEZONE = ZoneInfo("America/Vancouver")

logger = logging.getLogger(__name__)


class InviteListSheet:
    """
    Writes RSVPs to the Invite list, signed in as the Google service account the
    workbook is shared with.
    """

    def __init__(self, spreadsheet_id, service_account_key):
        """
        Open a workbook's Invite list, given the service account's key (a dict).
        """
        client = gspread.service_account_from_dict(service_account_key)
        self.worksheet = client.open_by_key(spreadsheet_id).worksheet(
            INVITE_LIST_WORKSHEET
        )

    def apply(self, event):
        """
        Write an RSVP event into its invitation's RSVP columns, in the row with its
        invite code.

        Raises ValueError if the Invite list is missing any of those columns. If no
        row has the invite code (the row was deleted), it's logged and skipped.
        """
        columns = column_numbers(self.worksheet.row_values(1))
        missing = [name for name in [INVITE_CODE, *RSVP_COLUMNS] if name not in columns]
        if missing:
            raise ValueError(
                f"The {INVITE_LIST_WORKSHEET} has no {', '.join(missing)} column;"
                " run make sheet-setup"
            )

        invite_code = event["invitation"]["invite_code"]
        codes = self.worksheet.col_values(columns[INVITE_CODE])
        rows = [
            row
            for row, code in enumerate(codes, start=1)
            if plain_code(code) == invite_code
        ]
        if not rows:
            logger.error(
                "No row in the %s has invite code %s",
                INVITE_LIST_WORKSHEET,
                invite_code,
            )
            return

        self.worksheet.batch_update(
            [
                {
                    "range": gspread.utils.rowcol_to_a1(rows[0], columns[name]),
                    "values": [[value]],
                }
                for name, value in rsvp_values(event["invitation"]).items()
            ]
        )


def rsvp_values(invitation):
    """
    An invitation's value for each of RSVP_COLUMNS: who's coming and not, counts of
    adults, children and each weekend event, and dietary needs and the note.
    """
    coming = [guest for guest in invitation["guests"] if guest["attending"]]
    not_coming = [guest for guest in invitation["guests"] if not guest["attending"]]
    responded = datetime.fromisoformat(invitation["responded_at"])
    return {
        "Responded": f"{responded.astimezone(TIMEZONE):%Y-%m-%d %H:%M}",
        "Coming": ", ".join(guest["name"] for guest in coming),
        "Not coming": ", ".join(guest["name"] for guest in not_coming),
        "Adults coming": sum(not guest["child"] for guest in coming),
        "Children coming": sum(guest["child"] for guest in coming),
        **{
            title: sum(coming_to(guest, event) for guest in coming)
            for event, title in EVENTS.items()
        },
        "Dietary": "; ".join(
            f"{guest['name']}: {guest['dietary']}"
            for guest in coming
            if guest["dietary"]
        ),
        "RSVP note": invitation["notes"],
    }
