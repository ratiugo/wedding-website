"""
Add the Invite list's new invitations to the invitations table: `make load-guests`.

Reads the Invite list tab (shared/invite_list.py) of the planning workbook
GOOGLE_SHEET_ID, signed in with the service account key at GOOGLE_KEY_FILE. Each row
is an invitation:

    Invitation     Its name, like "Morgan, Sam & Ellie".
    Guests         Their names, separated by commas.
    Children       Which of the Guests are children, separated by commas.
    Plus one       Yes to add a plus-one, named by Plus one name if known.
    Email          Where its emails go. Optional.
    Notes          Rows whose notes say "no invitation" are skipped.

Other columns are ignored. It shows what it would add and asks first. Invitations
already in the table are skipped; change those in the DynamoDB console. Then it
writes every invitation's code into the Invite code column, as printed on the cards.
"""

import json
import os
import re
import secrets
import sys

import boto3
import gspread

from invite_list import INVITE_CODE, INVITE_LIST_WORKSHEET, column_numbers, printed_code

# Letters and digits, minus the lookalikes 0/O and 1/I/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main():
    """
    Show the invitations the Invite list would add, add them if confirmed, and write
    every invitation's code into the sheet.
    """
    worksheet = open_invite_list()
    header, *rows = worksheet.get_all_values()
    invitations, problems = read_invite_list(header, rows)
    if INVITE_CODE not in header:
        problems.append(f"No {INVITE_CODE} column; run make sheet-setup first")
    if problems:
        print("The Invite list has problems, so nothing was loaded:")
        print("\n".join(f"  {problem}" for problem in problems))
        sys.exit(1)

    table = boto3.resource("dynamodb").Table(os.environ["INVITATIONS_TABLE"])
    items = get_invitations(table)
    loaded = {item["label"] for item in items}
    new = [
        invitation for invitation in invitations if invitation["label"] not in loaded
    ]

    print(
        f"{table.name}: {len(new)} to add, {len(invitations) - len(new)} already loaded"
    )
    for invitation in new:
        email = f" <{invitation['email']}>" if invitation["email"] else ""
        print(f"  + {invitation['label']}{email}: {describe(invitation['guests'])}")

    if new:
        answer = input(f"\nAdd these to {table.name}? Type yes to add: ")
        if answer.strip() != "yes":
            print("Nothing was added.")
            return
        items += add(table, new, {item["invite_code"] for item in items})
        print("Added.")
    write_codes(worksheet, header, invitations, items)
    print(f"Wrote each invitation's code to the {INVITE_CODE} column.")


def open_invite_list():
    """
    The planning workbook's Invite list worksheet.
    """
    with open(os.environ["GOOGLE_KEY_FILE"], encoding="utf-8") as key_file:
        client = gspread.service_account_from_dict(json.load(key_file))
    return client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).worksheet(
        INVITE_LIST_WORKSHEET
    )


def read_invite_list(header, rows):
    """
    The invitations in the Invite list's rows (below its header), in order, and a
    list of the rows' problems.

    Each invitation is {"label", "email", "guests", "row"}, with row its row number
    in the sheet and each guest {"name", "plus_one", "child"}.
    """
    missing = {"Invitation", "Guests"} - set(header)
    if missing:
        return [], [f"Missing column(s): {', '.join(sorted(missing))}"]

    invitations = []
    problems = []
    # Row 1 is the header.
    for number, values in enumerate(rows, start=2):
        row = {name: value.strip() for name, value in zip(header, values)}
        if not row.get("Invitation") or "no invitation" in row.get("Notes", "").lower():
            continue
        invitation, row_problems = read_row(row, f"Row {number}")
        invitation["row"] = number
        invitations.append(invitation)
        problems += row_problems

    labels = [invitation["label"] for invitation in invitations]
    problems += [
        f"{label} is in the list more than once"
        for label in sorted(set(labels))
        if labels.count(label) > 1
    ]
    return invitations, problems


def read_row(row, where):
    """
    An Invite list row's invitation, and a list of the row's problems.
    """
    names = split(row["Guests"])
    children = split(row.get("Children", ""))
    plus_one = row.get("Plus one", "").lower()
    email = row.get("Email", "")

    problems = []
    if not names:
        problems.append(f"{where}: needs Guests")
    problems += [
        f"{where}: {child} in Children isn't one of the Guests"
        for child in children
        if child not in names
    ]
    if plus_one not in ("", "yes", "no"):
        problems.append(f"{where}: Plus one should be Yes, No or blank, not {plus_one}")
    if email and not EMAIL.match(email):
        problems.append(f"{where}: {email} isn't an email address")

    guests = [
        {"name": name, "plus_one": False, "child": name in children} for name in names
    ]
    if plus_one == "yes":
        name = row.get("Plus one name") or "Plus-one"
        guests.append({"name": name, "plus_one": True, "child": False})
    return {"label": row["Invitation"], "email": email, "guests": guests}, problems


def split(names):
    """
    A comma-separated list of names, like "Morgan Rivera, Sam Rivera".
    """
    return [name.strip() for name in names.split(",") if name.strip()]


def add(table, invitations, taken):
    """
    Add the invitations, each with a new random code (none of the taken ones), and
    return their items.
    """
    items = []
    for invitation in invitations:
        code = new_code(taken)
        taken.add(code)
        item = new_item(invitation, code)
        table.put_item(
            Item=item, ConditionExpression="attribute_not_exists(invite_code)"
        )
        items.append(item)
    return items


def new_item(invitation, code):
    """
    The table item for a new invitation, with nobody having responded.
    """
    return {
        "invite_code": code,
        "label": invitation["label"],
        "email": invitation["email"] or None,
        "notes": "",
        "responded_at": None,
        "updates_opt_out": False,
        "guests": [
            {
                "id": number,
                "name": guest["name"],
                "plus_one": guest["plus_one"],
                "child": guest["child"],
                "attending": None,
                "events": {},
                "dietary": "",
            }
            for number, guest in enumerate(invitation["guests"], start=1)
        ],
    }


def new_code(taken):
    """
    A random invite code that isn't one of the taken codes.
    """
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if code not in taken:
            return code


def get_invitations(table):
    """
    Return every invitation in the table.
    """
    response = table.scan()
    items = response["Items"]
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items += response["Items"]
    return items


def describe(guests):
    """
    Guests on one line, like "Morgan Rivera, Ellie Rivera (child), Plus-one (plus-one)".
    """
    return ", ".join(
        guest["name"]
        + (" (plus-one)" if guest["plus_one"] else "")
        + (" (child)" if guest["child"] else "")
        for guest in guests
    )


def write_codes(worksheet, header, invitations, items):
    """
    Write each invitation's code, as printed on its card, into its row's Invite code
    cell.
    """
    column = column_numbers(header)[INVITE_CODE]
    codes = {item["label"]: item["invite_code"] for item in items}
    worksheet.batch_update(
        [
            {
                "range": gspread.utils.rowcol_to_a1(invitation["row"], column),
                "values": [[printed_code(codes[invitation["label"]])]],
            }
            for invitation in invitations
        ]
    )


if __name__ == "__main__":
    main()
