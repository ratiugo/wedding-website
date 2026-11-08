"""
The weekend events, besides the wedding, that guests coming to the wedding are asked
about, by id. Both Lambda images include this file, so the RSVP form, the API, the
Google Sheet and the emails all use this one list.
"""

EVENTS = {"bbq": "Friday BBQ", "brunch": "Sunday brunch"}


def coming_to(guest, event):
    """
    Whether a guest is coming to an event. Guests who aren't coming to the wedding,
    or who responded before the event was asked about, aren't.
    """
    return bool(guest["attending"] and guest.get("events", {}).get(event))
