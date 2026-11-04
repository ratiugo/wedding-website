"""
Lambda serving the website's RSVP form.

    GET  /rsvp/{invite_code}           Load an invitation, its guests, and any existing
                                       answers
    PUT  /rsvp/{invite_code}           Submit or update the answers
    POST /rsvp/{invite_code}/opt-out   Stop update emails (the link in each update)
"""

import json
import os

from invitation import BadRequest, Invitation

GET = "GET /rsvp/{invite_code}"
PUT = "PUT /rsvp/{invite_code}"
OPT_OUT = "POST /rsvp/{invite_code}/opt-out"

RSVP_OPEN = os.environ.get("RSVP_OPEN") == "true"


def lambda_handler(event, _context):
    """
    Load the invitation in the path, and on PUT save the request's answers to it, or
    on opt-out stop its update emails.
    """
    route = event.get("routeKey")
    if route not in (GET, PUT, OPT_OUT):
        return response(404, {"error": "Not found"})
    # Opting out works while RSVPs are closed, since updates can go out before then.
    if route != OPT_OUT and not RSVP_OPEN:
        return response(403, {"error": "RSVPs aren't open yet."})

    invitation = Invitation.get(event["pathParameters"]["invite_code"])
    if invitation is None:
        return response(404, {"error": "We couldn't find that invitation code."})

    if route == OPT_OUT:
        invitation.opt_out()
        return response(200, {"updates_opt_out": True})

    if route == PUT:
        return save_answers(invitation, event.get("body"))
    return response(200, invitation.view())


def save_answers(invitation, body):
    """
    Save the answers in a PUT's body, and respond with the saved invitation, or why
    the answers were rejected.
    """
    try:
        saved = invitation.respond(json.loads(body or ""))
    except json.JSONDecodeError:
        return response(400, {"error": "Body must be valid JSON."})
    except BadRequest as e:
        return response(400, {"error": str(e)})
    return response(200, saved.view())


def response(status, body):
    """
    Build an API Gateway JSON response.
    """
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
