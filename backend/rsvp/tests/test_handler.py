"""
RSVP API handler tests: turning requests into Invitation calls and results into
HTTP responses, with a mock in place of the Invitation class.
"""

import json
from unittest.mock import MagicMock

import pytest

import handler
from invitation import BadRequest


@pytest.fixture(name="invitations", autouse=True)
def invitations_fixture(monkeypatch):
    """
    A mock Invitation class, whose get returns an invitation viewed as {"label": ...}.
    """
    invitations = MagicMock()
    invitations.get.return_value.view.return_value = {"label": "Jamie"}
    monkeypatch.setattr(handler, "Invitation", invitations)
    monkeypatch.setattr(handler, "RSVP_OPEN", True)
    return invitations


def call(method, body=None):
    """
    Invoke the handler for invite code JAMIE2 the way API Gateway does, and return
    (status, body).
    """
    event = {
        "routeKey": f"{method} /rsvp/{{invite_code}}",
        "pathParameters": {"invite_code": "JAMIE2"},
        "body": body,
    }
    result = handler.lambda_handler(event, None)
    return result["statusCode"], json.loads(result["body"])


def test_get_returns_the_invitation(invitations):
    assert call("GET") == (200, {"label": "Jamie"})
    invitations.get.assert_called_once_with("JAMIE2")


def test_unknown_invite_code_is_not_found(invitations):
    invitations.get.return_value = None
    assert call("GET") == (404, {"error": "We couldn't find that invitation code."})


def test_put_responds_with_the_parsed_body(invitations):
    invitation = invitations.get.return_value
    invitation.respond.return_value.view.return_value = {"label": "Saved"}

    assert call("PUT", '{"guests": []}') == (200, {"label": "Saved"})
    invitation.respond.assert_called_once_with({"guests": []})


def test_put_with_invalid_json_is_a_bad_request():
    assert call("PUT", "not json") == (400, {"error": "Body must be valid JSON."})


def test_rejected_answers_are_a_bad_request_with_the_reason(invitations):
    invitations.get.return_value.respond.side_effect = BadRequest("Please answer.")
    assert call("PUT", '{"guests": []}') == (400, {"error": "Please answer."})


def test_nothing_is_looked_up_while_rsvps_are_closed(invitations, monkeypatch):
    monkeypatch.setattr(handler, "RSVP_OPEN", False)

    assert call("GET") == (403, {"error": "RSVPs aren't open yet."})
    invitations.get.assert_not_called()
