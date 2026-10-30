-- The database user the RSVP Lambda signs in as.
CREATE ROLE rsvp_app LOGIN;
GRANT rds_iam TO rsvp_app;
GRANT SELECT, UPDATE ON invitations, guests TO rsvp_app;
ALTER ROLE rsvp_app SET idle_session_timeout = '60s';
