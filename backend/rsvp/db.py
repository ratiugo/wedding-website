"""
DynamoDB access. Each invitation is one item, keyed by its invite code, with its guests
inside it:

    {
        "invite_code": "R7KM3QPX",
        "label": "Morgan, Sam & Ellie",
        "email": "morgan@example.com",
        "notes": "",
        "responded_at": None,
        "updates_opt_out": False,
        "guests": [
            {"id": 1, "name": "Morgan Rivera", "plus_one": False, "child": False,
             "attending": None, "events": {}, "dietary": ""},
            ...
        ],
    }
"""

from datetime import datetime, timezone

import boto3


class Database:
    """
    Reads invitations from, and saves responses to, a DynamoDB table.
    """

    def __init__(self, table_name):
        self.table = boto3.resource("dynamodb").Table(table_name)

    def get_invitation(self, invite_code):
        """
        Return the invitation, or None if there isn't one.
        """
        item = self.table.get_item(Key={"invite_code": invite_code}).get("Item")
        return with_int_ids(item) if item else None

    def save_response(self, invite_code, guests, notes, updates_opt_out):
        """
        Replace the invitation's guests, notes and opt-out, mark it as responded now,
        and return the saved invitation.
        """
        item = self.table.update_item(
            Key={"invite_code": invite_code},
            UpdateExpression=(
                "SET guests = :guests, notes = :notes, responded_at = :now,"
                " updates_opt_out = :updates_opt_out"
            ),
            ConditionExpression="attribute_exists(invite_code)",
            ExpressionAttributeValues={
                ":guests": guests,
                ":notes": notes,
                ":now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ":updates_opt_out": updates_opt_out,
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
        return with_int_ids(item)

    def opt_out(self, invite_code):
        """
        Mark an existing invitation as opted out of update emails.
        """
        self.table.update_item(
            Key={"invite_code": invite_code},
            UpdateExpression="SET updates_opt_out = :true",
            ConditionExpression="attribute_exists(invite_code)",
            ExpressionAttributeValues={":true": True},
        )


def with_int_ids(item):
    """
    The item with its guest ids as ints. DynamoDB returns every number as a Decimal,
    which json.dumps can't handle.
    """
    for guest in item["guests"]:
        guest["id"] = int(guest["id"])
    return item
