-- One invitation (one invite code, one card) has one or more guests.

CREATE TABLE IF NOT EXISTS invitations (
    id           SERIAL PRIMARY KEY,
    invite_code  TEXT NOT NULL UNIQUE,
    label        TEXT NOT NULL UNIQUE,    -- greeting on the card, e.g. "Jamie, Alex & Mia"
    notes        TEXT NOT NULL DEFAULT '',
    responded_at TIMESTAMPTZ             -- NULL until they respond
);

CREATE TABLE IF NOT EXISTS guests (
    id            SERIAL PRIMARY KEY,
    invitation_id INTEGER NOT NULL REFERENCES invitations(id),
    name          TEXT NOT NULL,
    plus_one      BOOLEAN NOT NULL DEFAULT false,  -- placeholder the invitee gets to name
    child         BOOLEAN NOT NULL DEFAULT false,
    attending     BOOLEAN,                         -- NULL until they respond
    dietary       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS guests_invitation_id_idx ON guests (invitation_id);
