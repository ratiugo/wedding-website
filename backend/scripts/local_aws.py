"""
Create the local fake AWS resources that `make start` needs: the RSVP bucket, and the
invitations table with the example invitations from data/guests.example.csv, a CSV
in the Invite list's layout (see load_guests.py).

Runs in the local-aws container, where AWS_ENDPOINT_URL points boto3 at the fake
(moto).
The fake keeps everything in memory, so it starts empty each time it's created.
"""

import csv
import os

import boto3

from load_guests import add, read_invite_list

EXAMPLES = "/data/guests.example.csv"


def main():
    """
    Create the bucket and table, add the example invitations to a new table, and
    print their RSVP links (their codes are random, so new each time).
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

    with open(EXAMPLES, encoding="utf-8", newline="") as file:
        header, *rows = csv.reader(file)
    invitations, problems = read_invite_list(header, rows)
    if problems:
        raise ValueError(f"{EXAMPLES} has problems: {problems}")
    print("Example invitations:")
    for item in add(table, invitations, set()):
        link = f"http://localhost:8080/rsvp?invite_code={item['invite_code']}"
        print(f"  {item['label']}: {link}")


if __name__ == "__main__":
    main()
