"""
Lambda serving the website's RSVP form.

    GET /rsvp/{invite_code}   Load an invitation, its guests, and any existing answers
    PUT /rsvp/{invite_code}   Submit or update the answers
"""

import json

from invitation import BadRequest, Invitation

GET = "GET /rsvp/{invite_code}"
PUT = "PUT /rsvp/{invite_code}"


def lambda_handler(event, _context):
    """
    Load the invitation in the path, and on PUT save the request's answers to it.
    """
    route = event.get("routeKey")
    if route not in (GET, PUT):
        return response(404, {"error": "Not found"})

    invitation = Invitation.get(event["pathParameters"]["invite_code"])
    if invitation is None:
        return response(404, {"error": "We couldn't find that invitation code."})

    if route == PUT:
        try:
            invitation = invitation.respond(json.loads(event.get("body") or ""))
        except json.JSONDecodeError:
            return response(400, {"error": "Body must be valid JSON."})
        except BadRequest as e:
            return response(400, {"error": str(e)})

    return response(200, invitation.view())


def response(status, body):
    """
    Build an API Gateway JSON response.
    """
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
