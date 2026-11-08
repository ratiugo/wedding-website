"""
Bring the invitations table up to date with the Invite list: `make load-guests`.

Reads the Invite list tab (shared/invite_list.py) of the planning workbook
GOOGLE_SHEET_ID, signed in with the service account key at GOOGLE_KEY_FILE. Each row
is an invitation:

    Invitation     Its name, like "Morgan, Sam & Ellie".
    Guests         Their names, separated by commas.
    Children       Which of the Guests are children, separated by commas.
    Plus one       Yes to add a plus-one, named by Plus one name if known.
    Email          Where its emails go. Optional.
    Notes          Rows whose notes say "no invitation" are skipped.

Other columns are ignored. Rows are matched to the table by their Invite code, or by
name for rows without one. It shows a plan and asks before changing anything:

    +  Rows not in the table are added, with new codes.
    ~  Renamed invitations and changed emails are updated, and so are guests (names,
       children, plus-ones) for invitations that haven't RSVP'd.
    !  Guest changes for invitations that have RSVP'd, and invitations that are no
       longer in the list, are left as they are: change those in the DynamoDB console.

Nothing is deleted, and plus-one names aren't compared, since guests give them when
they RSVP. Then it writes every invitation's code into the Invite code column, as
printed on the cards.
"""

import json
import os
import re
import secrets
import sys

import boto3
import gspread

from invite_list import (
    INVITE_CODE,
    INVITE_LIST_WORKSHEET,
    column_numbers,
    plain_code,
    printed_code,
)

# Letters and digits, minus the lookalikes 0/O and 1/I/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main():
    """
    Show how the table differs from the Invite list, apply the changes if confirmed,
    and write every invitation's code into the sheet.
    """
    worksheet = open_invite_list()
    header, *rows = worksheet.get_all_values()
    invitations, problems = read_invite_list(header, rows)
    if INVITE_CODE not in header:
        problems.append(f"No {INVITE_CODE} column; run make sheet-setup first")

    table = boto3.resource("dynamodb").Table(os.environ["INVITATIONS_TABLE"])
    items = get_invitations(table)
    plan = make_plan(invitations, items)
    problems += plan["problems"]
    if problems:
        print("The Invite list has problems, so nothing was changed:")
        print("\n".join(f"  {problem}" for problem in problems))
        sys.exit(1)

    print_plan(table.name, plan)
    if plan["new"] or plan["changes"]:
        answer = input(f"\nApply these to {table.name}? Type yes to apply: ")
        if answer.strip() != "yes":
            print("Nothing was changed.")
            return
        taken = {item["invite_code"] for item in items}
        for invitation, item in zip(plan["new"], add(table, plan["new"], taken)):
            plan["matched"].append((invitation, item))
        for item, fields, _ in plan["changes"]:
            update(table, item, fields)
        print("Applied.")
    write_codes(worksheet, header, plan["matched"])
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

    Each invitation is {"label", "email", "guests", "row", "code"}, with row its row
    number in the sheet, code its invite code (blank if it has none yet) and each
    guest {"name", "plus_one", "child"}.
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
        invitation["code"] = plain_code(row.get(INVITE_CODE, ""))
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


def make_plan(invitations, items):
    """
    Compare the Invite list's invitations with the table's items.

    Returns {"new", "matched", "changes", "warnings", "problems"}: the invitations
    to add, each (invitation, item) pair, each (item, fields, descriptions) to change,
    and lines about what's left alone and what stops the load.
    """
    by_code = {item["invite_code"]: item for item in items}
    by_label = {item["label"]: item for item in items}
    plan = {"new": [], "matched": [], "changes": [], "warnings": [], "problems": []}

    for invitation in invitations:
        if invitation["code"] and invitation["code"] not in by_code:
            plan["problems"].append(
                f"Row {invitation['row']}: {printed_code(invitation['code'])}"
                " isn't in the table"
            )
            continue
        item = by_code.get(invitation["code"]) or by_label.get(invitation["label"])
        if not item:
            plan["new"].append(invitation)
            continue
        plan["matched"].append((invitation, item))
        fields, descriptions, warning = differences(invitation, item)
        if fields:
            plan["changes"].append((item, fields, descriptions))
        if warning:
            plan["warnings"].append(warning)

    in_list = {item["invite_code"] for _, item in plan["matched"]}
    plan["warnings"] += [
        f"{item['label']} ({printed_code(item['invite_code'])}) isn't in the Invite"
        " list, so it's left as is"
        for item in items
        if item["invite_code"] not in in_list
    ]
    return plan


def differences(invitation, item):
    """
    How an item differs from its invitation in the Invite list.

    Returns (fields, descriptions, warning): the fields to set, a line describing
    each, and a warning if its guests differ but it has already RSVP'd.
    """
    fields = {}
    descriptions = []
    if invitation["label"] != item["label"]:
        fields["label"] = invitation["label"]
        descriptions.append(f"renamed from {item['label']}")
    email = invitation["email"] or None
    if email != item.get("email"):
        fields["email"] = email
        descriptions.append(f"email {item.get('email') or 'none'} → {email or 'none'}")

    guests = new_item(invitation, item["invite_code"])["guests"]
    if list(map(compared, guests)) == list(map(compared, item["guests"])):
        return fields, descriptions, None
    change = f"{describe(item['guests'])} → {describe(guests)}"
    if item["responded_at"]:
        warning = f"{invitation['label']} has RSVP'd, so its guests weren't changed:"
        return fields, descriptions, f"{warning} {change}"
    fields["guests"] = guests
    descriptions.append(f"guests {change}")
    return fields, descriptions, None


def compared(guest):
    """
    The parts of a guest that the Invite list sets: name (except for plus-ones,
    whose names guests give when they RSVP), plus-one and child.
    """
    return (
        None if guest["plus_one"] else guest["name"],
        guest["plus_one"],
        guest["child"],
    )


def print_plan(table_name, plan):
    """
    Print what loading would add and change, and what it leaves alone.
    """
    unchanged = len(plan["matched"]) - len(plan["changes"])
    print(
        f"{table_name}: {len(plan['new'])} to add, {len(plan['changes'])} to change,"
        f" {unchanged} unchanged"
    )
    for invitation in plan["new"]:
        email = f" <{invitation['email']}>" if invitation["email"] else ""
        print(f"  + {invitation['label']}{email}: {describe(invitation['guests'])}")
    for item, fields, descriptions in plan["changes"]:
        print(f"  ~ {fields.get('label', item['label'])}: {'; '.join(descriptions)}")
    for warning in plan["warnings"]:
        print(f"  ! {warning}")


def update(table, item, fields):
    """
    Set fields on an item in the table.
    """
    table.update_item(
        Key={"invite_code": item["invite_code"]},
        UpdateExpression="SET " + ", ".join(f"#{name} = :{name}" for name in fields),
        ExpressionAttributeNames={f"#{name}": name for name in fields},
        ExpressionAttributeValues={f":{name}": value for name, value in fields.items()},
    )


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


def write_codes(worksheet, header, matched):
    """
    Write each matched invitation's code, as printed on its card, into its row's
    Invite code cell.
    """
    column = column_numbers(header)[INVITE_CODE]
    worksheet.batch_update(
        [
            {
                "range": gspread.utils.rowcol_to_a1(invitation["row"], column),
                "values": [[printed_code(item["invite_code"])]],
            }
            for invitation, item in matched
        ]
    )


if __name__ == "__main__":
    main()
