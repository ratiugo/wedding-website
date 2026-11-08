"""
Set up the planning workbook for the website (make sheet-setup): add the Invite code
and RSVP columns to its Invite list, and an RSVP summary tab.

Runs in the notifier image, signed in with the service account key at
GOOGLE_KEY_FILE, against the workbook GOOGLE_SHEET_ID, which must already have an
Invite list (shared/invite_list.py) with its Invitation and People columns. Only
missing columns and tabs are added, so it's safe to run again. The columns go after
the last column in use (past any notes or totals to the right of the list), leaving
one blank column between.
"""

import json
import os

import gspread

from events import EVENTS
from invite_list import INVITE_CODE, RSVP_COLUMNS, TAB, column_numbers

SUMMARY_TAB = "RSVP summary"
# The website's column headers are shaded, to set them apart from the columns we edit.
WEBSITE_HEADER = {
    "textFormat": {"bold": True},
    "backgroundColor": {"red": 0.89, "green": 0.87, "blue": 0.84},
}
WEBSITE_NOTE = "Filled in by the website. Don't edit these columns."


def add_columns(worksheet):
    """
    Add whichever of the Invite code and RSVP columns the Invite list is missing, and
    return its header row.
    """
    header = worksheet.row_values(1)
    missing = [name for name in [INVITE_CODE, *RSVP_COLUMNS] if name not in header]
    if not missing:
        return header

    last_used = max(len(row) for row in worksheet.get_all_values())
    first = last_used + 2
    needed = first + len(missing) - 1
    if worksheet.col_count < needed:
        worksheet.add_cols(needed - worksheet.col_count)
    start = gspread.utils.rowcol_to_a1(1, first)
    end = gspread.utils.rowcol_to_a1(1, needed)
    worksheet.update(values=[missing], range_name=f"{start}:{end}")
    return worksheet.row_values(1)


def mark_columns(worksheet, header):
    """
    Shade the website's column headers, and note on the Invite code header not to
    edit them, wherever the columns have been moved to.
    """
    columns = column_numbers(header)
    cells = [
        gspread.utils.rowcol_to_a1(1, columns[name])
        for name in [INVITE_CODE, *RSVP_COLUMNS]
    ]
    worksheet.batch_format(
        [{"range": cell, "format": WEBSITE_HEADER} for cell in cells]
    )
    worksheet.update_note(cells[0], WEBSITE_NOTE)


def summary(header):
    """
    The RSVP summary tab's blocks, by their top-left cell: counts of invitations,
    guests, drinks and weekend events (labels in column A, formulas in B), and the
    dietary needs and guests' notes, each listed by invitation as RSVPs come in.

    Each formula reads the Invite list directly, so the blocks can be moved. Only
    invitations with a code are counted, and guest counts use the People column
    (each invitation's number of guests). Counts of the columns we edit by hand,
    like Invitation sent, are left out when the column isn't there.
    """
    columns = column_numbers(header)

    def column(name):
        """
        An Invite list column below its header, like 'Invite list'!U2:U.
        """
        letter = gspread.utils.rowcol_to_a1(1, columns[name]).rstrip("1")
        return f"'{TAB}'!{letter}2:{letter}"

    def listed(name):
        """
        A list of each invitation's value in a column, where it has one.
        """
        return (
            f"=IFERROR(FILTER({{{column('Invitation')},{column(name)}}},"
            f'{column(name)}<>""),"None yet")'
        )

    def if_column(name, *rows):
        """
        The rows if the Invite list has the column, otherwise none.
        """
        return list(rows) if name in columns else []

    code, responded, people = column(INVITE_CODE), column("Responded"), column("People")
    coming = f"SUM({column('Adults coming')})+SUM({column('Children coming')})"

    def invited(*conditions):
        """
        A formula for the number of guests on invitations with a code, and with
        each (column, value) condition, like ("Bride/Groom", "Bride").
        """
        extra = "".join(f',{column(name)},"{value}"' for name, value in conditions)
        return f'=SUMIFS({people},{code},"<>"{extra})'

    return {
        "A1": [
            ["Invitations"],
            ["Total", f"=COUNTA({code})"],
            *if_column(
                "Save the date sent",
                [
                    "Save the dates sent",
                    f"=COUNTIF({column('Save the date sent')},TRUE)",
                ],
            ),
            *if_column(
                "Invitation sent",
                ["Invitations sent", f"=COUNTIF({column('Invitation sent')},TRUE)"],
            ),
            ["Responded", f"=COUNTA({responded})"],
            ["Awaiting reply", f"=COUNTA({code})-COUNTA({responded})"],
            [],
            ["Guests"],
            ["Invited", invited()],
            *if_column(
                "Bride/Groom",
                *[
                    [label, invited(("Bride/Groom", side))]
                    for label, side in (
                        ("Bride's side", "Bride"),
                        ("Groom's side", "Groom"),
                        ("Both sides", "Both"),
                    )
                ],
            ),
            *if_column(
                "Plus one",
                ["Plus-ones", f'=COUNTIFS({column("Plus one")},"Yes",{code},"<>")'],
            ),
            ["Coming", f"={coming}"],
            ["Adults coming", f"=SUM({column('Adults coming')})"],
            ["Children coming", f"=SUM({column('Children coming')})"],
            ["Not coming", f'=SUMIFS({people},{responded},"<>")-({coming})'],
            ["Awaiting reply", invited(("Responded", ""))],
            [],
            *if_column(
                "Drink estimate",
                ["Drinks"],
                ["Drink estimate", f"=SUM({column('Drink estimate')})"],
                [],
            ),
            ["Extra Events"],
            *[[title, f"=SUM({column(title)})"] for title in EVENTS.values()],
        ],
        "D1": [["Dietary needs"], [listed("Dietary")]],
        "G1": [["Notes from guests"], [listed("RSVP note")]],
    }


def create_summary(spreadsheet, header):
    """
    Add the RSVP summary tab, with bold headings and columns wide enough to read.
    """
    worksheet = spreadsheet.add_worksheet(SUMMARY_TAB, rows=200, cols=8)
    blocks = summary(header)
    worksheet.batch_update(
        [{"range": cell, "values": rows} for cell, rows in blocks.items()],
        value_input_option="USER_ENTERED",
    )
    headings = [
        f"A{row}" for row, cells in enumerate(blocks["A1"], start=1) if len(cells) == 1
    ]
    for cells in [*headings, "D1", "G1"]:
        worksheet.format(cells, {"textFormat": {"bold": True}})
    widths = [200, 80, 30, 200, 300, 30, 200, 300]
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": worksheet.id,
                            "dimension": "COLUMNS",
                            "startIndex": index,
                            "endIndex": index + 1,
                        },
                        "properties": {"pixelSize": width},
                        "fields": "pixelSize",
                    }
                }
                for index, width in enumerate(widths)
            ]
        }
    )


def main():
    """
    Add the Invite list's missing columns, mark the website's columns, and add the
    RSVP summary tab if it's missing.
    """
    with open(os.environ["GOOGLE_KEY_FILE"], encoding="utf-8") as key_file:
        client = gspread.service_account_from_dict(json.load(key_file))
    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])

    worksheet = spreadsheet.worksheet(TAB)
    header = add_columns(worksheet)
    mark_columns(worksheet, header)
    print(f"{TAB} has the {INVITE_CODE} and RSVP columns")
    if SUMMARY_TAB in [tab.title for tab in spreadsheet.worksheets()]:
        print(f"{SUMMARY_TAB} already exists, left as is")
    else:
        create_summary(spreadsheet, header)
        print(f"Created {SUMMARY_TAB}")


if __name__ == "__main__":
    main()
