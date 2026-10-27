"""
Postgres access. See schema.sql for the tables.
"""

import time

import boto3
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

CONNECT_TIMEOUT = 5
CONNECT_DEADLINE = 25

GET_INVITATION = """
    SELECT i.id AS invitation_id, i.invite_code, i.label, i.notes, i.responded_at,
           g.id, g.name, g.plus_one, g.child, g.attending, g.dietary
    FROM invitations i
    JOIN guests g ON g.invitation_id = i.id
    WHERE i.invite_code = %s
    ORDER BY g.id
"""

SAVE_RESPONSE = """
    WITH answers (id, attending, dietary, plus_one_name) AS (
        SELECT * FROM unnest(
            %(ids)s::integer[],
            %(attending)s::boolean[],
            %(dietary)s::text[],
            %(plus_one_names)s::text[]
        )
    ),
    saved_guests AS (
        UPDATE guests
        SET attending = answers.attending,
            dietary = answers.dietary,
            name = COALESCE(answers.plus_one_name, guests.name)
        FROM answers
        WHERE guests.id = answers.id AND guests.invitation_id = %(invitation_id)s
    )
    UPDATE invitations
    SET notes = %(notes)s, responded_at = now()
    WHERE id = %(invitation_id)s
"""

GUEST_FIELDS = ("id", "name", "plus_one", "child", "attending", "dietary")


class Database:
    """
    Postgres queries for the RSVP API.

    With iam_auth, each new connection signs in as the URL's user with an RDS IAM
    token. Connecting retries for up to CONNECT_DEADLINE seconds, long enough for
    Aurora to resume from a pause, and a query whose connection was dropped reconnects
    and runs again.
    """

    def __init__(self, url, iam_auth=False):
        self.url = url
        self.iam_auth = iam_auth
        self._conn = None

    def connection(self):
        """
        Return the open connection, connecting if there isn't a usable one.
        """
        if self._conn is None or self._conn.closed:
            self._conn = self.connect()
        return self._conn

    def connect(self):
        """
        Open a new connection, retrying until CONNECT_DEADLINE if it fails.
        """
        deadline = time.monotonic() + CONNECT_DEADLINE
        while True:
            try:
                return psycopg.connect(
                    self.url,
                    autocommit=True,
                    row_factory=dict_row,
                    connect_timeout=CONNECT_TIMEOUT,
                    password=self.iam_token() if self.iam_auth else None,
                )
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)

    def iam_token(self):
        """
        An RDS IAM token to sign in as the URL's user, used as the password.

        Tokens expire after 15 minutes, so each new connection gets a fresh one. It's
        signed locally with the Lambda's role, so creating it needs no network access.
        """
        params = conninfo_to_dict(self.url)
        return boto3.client("rds").generate_db_auth_token(
            DBHostname=params["host"],
            Port=int(params.get("port", 5432)),
            DBUsername=params["user"],
        )

    def close(self):
        """
        Close the connection, if one is open.
        """
        if self._conn is not None:
            self._conn.close()

    def query(self, sql, params=()):
        """
        Run one SQL statement and return its rows (empty for one that returns none).

        If the connection was dropped, this reconnects and runs it once more. Each
        statement commits on its own, so a change made by one statement is all or
        nothing.
        """
        try:
            cursor = self.connection().execute(sql, params)
        except psycopg.OperationalError:
            if self._conn is None or not self._conn.broken:
                raise
            self.close()
            cursor = self.connection().execute(sql, params)
        return cursor.fetchall() if cursor.description else []

    def get_invitation(self, invite_code):
        """
        Return the invitation with its guests, or None if there isn't one.

        The JOIN returns a row per guest, each repeating the invitation's columns,
        so the invitation fields come from the first row.
        """
        rows = self.query(GET_INVITATION, (invite_code,))
        if not rows:
            return None

        first = rows[0]
        return {
            "id": first["invitation_id"],
            "invite_code": first["invite_code"],
            "label": first["label"],
            "notes": first["notes"],
            "responded_at": first["responded_at"],
            "guests": [{k: row[k] for k in GUEST_FIELDS} for row in rows],
        }

    def save_response(self, invitation_id, guests, notes):
        """
        Save every guest's answer and the invitation's notes, in one statement.

        The answers are passed as one array per field, which unnest turns back into
        rows to update the guests from. A plus_one_name of None keeps the guest's
        name. Only guests on this invitation are updated.
        """
        self.query(
            SAVE_RESPONSE,
            {
                "ids": [guest["id"] for guest in guests],
                "attending": [guest["attending"] for guest in guests],
                "dietary": [guest["dietary"] for guest in guests],
                "plus_one_names": [guest["plus_one_name"] for guest in guests],
                "invitation_id": invitation_id,
                "notes": notes,
            },
        )
