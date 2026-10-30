"""
DynamoDB access. Each invitation is one item, keyed by its invite code, with its guests
inside it:

    {
        "invite_code": "RIVERA",
        "label": "Morgan, Sam & Ellie",
        "notes": "",
        "responded_at": None,
        "guests": [
            {"id": 1, "name": "Morgan Rivera", "plus_one": False, "child": False,
             "attending": None, "dietary": ""},
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

    def save_response(self, invite_code, guests, notes):
        """
        Replace the invitation's guests and notes, mark it as responded now, and
        return the saved invitation.
        """
        item = self.table.update_item(
            Key={"invite_code": invite_code},
            UpdateExpression=(
                "SET guests = :guests, notes = :notes, responded_at = :now"
            ),
            ConditionExpression="attribute_exists(invite_code)",
            ExpressionAttributeValues={
                ":guests": guests,
                ":notes": notes,
                ":now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
        return with_int_ids(item)


def with_int_ids(item):
    """
    The item with its guest ids as ints. DynamoDB returns every number as a Decimal,
    which json.dumps can't handle.
    """
    for guest in item["guests"]:
        guest["id"] = int(guest["id"])
    return item
