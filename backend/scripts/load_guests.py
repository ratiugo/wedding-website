"""
Add a guest list's new invitations to the invitations table: `make load-guests`.

The guest list is a CSV with a row per guest, in the format of
data/guests.example.csv. Rows with the same invitation name make one invitation.

It shows what it would add and asks first. Invitations already
in the table are skipped; change those in the DynamoDB console. It then writes each
invitation's code and RSVP link to the --codes file, for the cards.
"""

import argparse
import csv
import os
import re
import secrets
import sys

import boto3

# Letters and digits, minus the lookalikes 0/O and 1/I/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main():
    """
    Show the invitations the guest list would add, and add them if confirmed.
    """
    parser = argparse.ArgumentParser(description="Load a guest list into DynamoDB.")
    parser.add_argument("guest_list", help="the guest list CSV")
    parser.add_argument("--codes", required=True, help="CSV to write codes to")
    args = parser.parse_args()

    invitations, problems = read_guest_list(args.guest_list)
    if problems:
        print("The guest list has problems, so nothing was loaded:")
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
    write_codes(args.codes, invitations, items, os.environ["SITE_URL"])
    print(f"Wrote each invitation's code and RSVP link to {args.codes}.")


def read_guest_list(path):
    """
    The invitations in a guest list CSV, in order, and a list of its problems.

    Each invitation is {"label", "email", "guests"}, with each guest
    {"name", "plus_one", "child"}.
    """
    invitations = {}
    problems = []
    with open(path, encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing = {"invitation", "name"} - set(reader.fieldnames or [])
        if missing:
            return [], [f"Missing column(s): {', '.join(sorted(missing))}"]
        # Row 1 is the header.
        for row_number, row in enumerate(reader, start=2):
            problems += add_row(invitations, row, f"Row {row_number}")
    return list(invitations.values()), problems


def add_row(invitations, row, where):
    """
    Add a CSV row's guest to its invitation, and return any problems with the row.
    """
    row = {column: (value or "").strip() for column, value in row.items()}
    label, name, email = row["invitation"], row["name"], row.get("email", "")
    if not label or not name:
        return [f"{where}: needs an invitation and a name"]

    problems = []
    flags = {}
    for column in ("plus_one", "child"):
        value = row.get(column, "").lower()
        if value not in ("", "yes"):
            problems.append(f"{where}: {column} should be blank or yes, not {value}")
        flags[column] = value == "yes"
    if email and not EMAIL.match(email):
        problems.append(f"{where}: {email} isn't an email address")

    invitation = invitations.setdefault(
        label, {"label": label, "email": "", "guests": []}
    )
    if email and invitation["email"] and email != invitation["email"]:
        problems.append(f"{where}: {label} already has a different email")
    invitation["email"] = invitation["email"] or email
    invitation["guests"].append({"name": name, **flags})
    return problems


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


def write_codes(path, invitations, items, site_url):
    """
    Write each invitation's code, as printed on its card, and RSVP link to a CSV.
    """
    codes = {item["label"]: item["invite_code"] for item in items}
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["invitation", "code", "link"])
        for invitation in invitations:
            code = codes[invitation["label"]]
            writer.writerow(
                [
                    invitation["label"],
                    f"{code[:4]}-{code[4:]}",
                    f"{site_url}/rsvp?invite_code={code}",
                ]
            )


if __name__ == "__main__":
    main()
