-- Example guests for local development, loaded after schema.sql when the Postgres
-- container is first created. The tables are new, so invitation ids are 1, 2 and 3,
-- and guest ids follow the order below (1-3 Riveras, 4-5 Shahs, 6-7 Jamie).
INSERT INTO invitations (invite_code, label) VALUES
    ('RIVERA', 'Morgan, Sam & Ellie'),
    ('SHAHPD', 'Priya & Dev'),
    ('JAMIE2', 'Jamie');

INSERT INTO guests (invitation_id, name, plus_one, child) VALUES
    (1, 'Morgan Rivera', false, false),
    (1, 'Sam Rivera', false, false),
    (1, 'Ellie Rivera', false, true),
    (2, 'Priya Shah', false, false),
    (2, 'Dev Shah', false, false),
    (3, 'Jamie Lee', false, false),
    (3, 'Plus-one', true, false);
