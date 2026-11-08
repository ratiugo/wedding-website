"""
The planning workbook's Invite list tab: one row per invitation, which we edit by
hand. The guest loader reads it and writes each invitation's code back, and the
notifier fills in the RSVP columns on each response.

Columns are found by their header in row 1, so they can be moved or reordered.
"""

import re

from events import EVENTS

# The worksheet (tab) in the planning workbook.
INVITE_LIST_WORKSHEET = "Invite list"

# The website's columns, which are never edited by hand. The guest loader writes each
# invitation's code, and the notifier writes the RSVP columns from guests' answers.
# Each is named once here, so a column can be renamed by changing it here.
INVITE_CODE = "Invite code"
RSVP_COLUMNS = [
    "Responded",
    "Coming",
    "Not coming",
    "Adults coming",
    "Children coming",
    *EVENTS.values(),
    "Dietary",
    "RSVP note",
]


def column_numbers(header):
    """
    Each header's column number (from 1), given row 1's values.
    """
    return {name: number for number, name in enumerate(header, start=1) if name}


def printed_code(code):
    """
    An invite code as printed on the cards, like H7KM-3QPX.
    """
    return f"{code[:4]}-{code[4:]}"


def plain_code(text):
    """
    An invite code without its hyphen or anything else that isn't a letter or digit.
    """
    return re.sub(r"[^A-Z0-9]", "", text.upper())
