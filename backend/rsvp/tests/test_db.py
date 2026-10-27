"""
Database connection tests.
"""

from unittest.mock import MagicMock

import psycopg
import pytest

import db
from db import Database

URL = "postgresql://rsvp_app@aurora:5432/wedding"


def dropped_connection():
    """
    A mock connection the server has dropped: queries fail, and it says it's broken.
    """
    conn = MagicMock(closed=False, broken=True)
    conn.execute.side_effect = psycopg.OperationalError("server closed the connection")
    conn.close.side_effect = lambda: setattr(conn, "closed", True)
    return conn


def test_a_dropped_connection_reconnects_and_runs_the_query_again(monkeypatch):
    fresh = MagicMock(closed=False)
    monkeypatch.setattr(
        psycopg, "connect", MagicMock(side_effect=[dropped_connection(), fresh])
    )

    Database(URL).query("SELECT 1")

    fresh.execute.assert_called_once_with("SELECT 1", ())


def test_connect_retries_until_the_database_answers(monkeypatch):
    resuming = psycopg.OperationalError("the database is resuming")
    connect = MagicMock(side_effect=[resuming, resuming, "connection"])
    monkeypatch.setattr(psycopg, "connect", connect)
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)

    assert Database(URL).connect() == "connection"
    assert connect.call_count == 3


def test_connect_gives_up_after_the_deadline(monkeypatch):
    unreachable = psycopg.OperationalError("the database is unreachable")
    monkeypatch.setattr(psycopg, "connect", MagicMock(side_effect=unreachable))
    monkeypatch.setattr(db, "CONNECT_DEADLINE", 0)

    with pytest.raises(psycopg.OperationalError):
        Database(URL).connect()


def test_iam_auth_signs_in_with_a_token_for_the_urls_user(monkeypatch):
    rds = MagicMock()
    rds.generate_db_auth_token.return_value = "token"
    monkeypatch.setattr(db.boto3, "client", lambda service: rds)
    connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", connect)

    Database(URL, iam_auth=True).connect()

    rds.generate_db_auth_token.assert_called_once_with(
        DBHostname="aurora", Port=5432, DBUsername="rsvp_app"
    )
    assert connect.call_args.kwargs["password"] == "token"
