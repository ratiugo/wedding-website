"""
Set up the wedding planning Google Sheet's Guests and Summary tabs (make sheet-setup).

Runs in the notifier image, signed in with the service account key at
GOOGLE_KEY_FILE, against the spreadsheet GOOGLE_SHEET_ID. Only missing tabs are
created, so existing rows and edited cost cells are left alone; delete a tab and run
this again to recreate it.

Guests gets HEADER (from sheets.py) as a bold, frozen header row, and wrapping for
the Dietary and Note columns. Summary gets formulas over the Guests columns. Both
get fixed column widths, wide enough to read without resizing.
"""

import json
import os

import gspread

from sheets import HEADER

GUESTS_COLUMN_WIDTHS = [220, 100, 160, 100, 60, 80, 200, 300, 140]
SUMMARY_COLUMN_WIDTHS = [260, 120]

SUMMARY = [
    ["Guests"],
    ["Responded", "=COUNTA(Guests!C:C)-1"],
    ["Coming", '=COUNTIF(Guests!D:D,"Coming")'],
    ["Not coming", '=COUNTIF(Guests!D:D,"Not coming")'],
    ["Adults coming", '=COUNTIFS(Guests!D:D,"Coming",Guests!E:E,"No")'],
    ["Children coming", '=COUNTIFS(Guests!D:D,"Coming",Guests!E:E,"Yes")'],
    [],
    ["Catering"],
    ["Cost per adult", 0],
    ["Cost per child", 0],
    ["Estimated catering total", "=B5*B9+B6*B10"],
    [],
    ["Dietary needs (guests coming)"],
    [
        '=IFERROR(FILTER({Guests!C:C,Guests!G:G},Guests!D:D="Coming",'
        'Guests!G:G<>""),"None yet")'
    ],
]


def create_guests(spreadsheet):
    """
    Add the Guests tab with its header row, column widths and wrapping.
    """
    worksheet = spreadsheet.add_worksheet("Guests", rows=1000, cols=len(HEADER))
    worksheet.update(values=[HEADER], range_name="A1")
    worksheet.format("1:1", {"textFormat": {"bold": True}})
    worksheet.freeze(rows=1)
    worksheet.format("G:H", {"wrapStrategy": "WRAP"})
    set_column_widths(spreadsheet, worksheet, GUESTS_COLUMN_WIDTHS)


def create_summary(spreadsheet):
    """
    Add the Summary tab, with its labels in column A and formulas in column B.
    """
    worksheet = spreadsheet.add_worksheet("Summary", rows=100, cols=2)
    worksheet.update(values=SUMMARY, range_name="A1", value_input_option="USER_ENTERED")
    set_column_widths(spreadsheet, worksheet, SUMMARY_COLUMN_WIDTHS)


def set_column_widths(spreadsheet, worksheet, widths):
    """
    Set a tab's columns, from A, to the given pixel widths.
    """
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
    Create whichever of the Guests and Summary tabs the spreadsheet is missing.
    """
    with open(os.environ["GOOGLE_KEY_FILE"], encoding="utf-8") as key_file:
        client = gspread.service_account_from_dict(json.load(key_file))
    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    existing = [worksheet.title for worksheet in spreadsheet.worksheets()]
    for title, create in (("Guests", create_guests), ("Summary", create_summary)):
        if title in existing:
            print(f"{title} already exists, left as is")
        else:
            create(spreadsheet)
            print(f"Created {title}")


if __name__ == "__main__":
    main()
