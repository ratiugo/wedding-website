"""
Create the local fake AWS resources that `make start` needs: the RSVP bucket, and the
invitations table with the example invitations from data/invitations.example.json.

Runs in the rsvp container, where AWS_ENDPOINT_URL points boto3 at the fake (moto).
The fake keeps everything in memory, so it starts empty each time it's created.
"""

import json
import os
from pathlib import Path

import boto3

EXAMPLES = Path("/data/invitations.example.json")


def main():
    """
    Create the bucket and table, and add the example invitations to a new table.
    """
    boto3.client("s3").create_bucket(Bucket=os.environ["RSVP_BUCKET"])

    dynamodb = boto3.resource("dynamodb")
    try:
        table = dynamodb.create_table(
            TableName=os.environ["INVITATIONS_TABLE"],
            KeySchema=[{"AttributeName": "invite_code", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "invite_code", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        print("Invitations table already exists, left as is")
        return

    for example in json.loads(EXAMPLES.read_text(encoding="utf-8")):
        table.put_item(Item=invitation(example))


def invitation(example):
    """
    A full invitation item from an example, which only gives the invite code, label,
    and each guest's name (plus plus_one or child when true).
    """
    return {
        "invite_code": example["invite_code"],
        "label": example["label"],
        "notes": "",
        "responded_at": None,
        "guests": [
            {
                "id": number,
                "name": guest["name"],
                "plus_one": guest.get("plus_one", False),
                "child": guest.get("child", False),
                "attending": None,
                "dietary": "",
            }
            for number, guest in enumerate(example["guests"], start=1)
        ],
    }


if __name__ == "__main__":
    main()
