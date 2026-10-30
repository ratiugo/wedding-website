"""
Database tests, with a mock in place of the DynamoDB table.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from db import Database

ITEM = {
    "invite_code": "TEST01",
    "label": "Jamie",
    "notes": "",
    "responded_at": None,
    "guests": [
        {
            "id": Decimal(1),
            "name": "Jamie Lee",
            "plus_one": False,
            "child": False,
            "attending": None,
            "dietary": "",
        }
    ],
}


@pytest.fixture(name="table")
def table_fixture():
    """
    A mock DynamoDB table.
    """
    return MagicMock()


@pytest.fixture(name="database")
def database_fixture(table):
    """
    A Database using the mock table.
    """
    database = Database("invitations")
    database.table = table
    return database


def test_get_invitation_returns_the_item_with_int_guest_ids(database, table):
    table.get_item.return_value = {"Item": ITEM}

    invitation = database.get_invitation("TEST01")

    table.get_item.assert_called_once_with(Key={"invite_code": "TEST01"})
    assert invitation["guests"][0]["id"] == 1
    assert isinstance(invitation["guests"][0]["id"], int)


def test_get_unknown_invitation_returns_none(database, table):
    table.get_item.return_value = {}
    assert database.get_invitation("ZZZZZZ") is None


def test_save_response_updates_only_an_existing_invitation(database, table):
    table.update_item.return_value = {"Attributes": ITEM}
    guests = [{"id": 1, "attending": True}]

    saved = database.save_response("TEST01", guests, "See you there")

    kwargs = table.update_item.call_args.kwargs
    assert kwargs["Key"] == {"invite_code": "TEST01"}
    assert kwargs["ConditionExpression"] == "attribute_exists(invite_code)"
    assert kwargs["ExpressionAttributeValues"][":guests"] == guests
    assert kwargs["ExpressionAttributeValues"][":notes"] == "See you there"
    assert saved["guests"][0]["id"] == 1
