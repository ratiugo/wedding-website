"""
Sample data for the notifier tests.
"""


def guest(name, attending, **fields):
    """
    A guest as it appears in an RSVP event.
    """
    return {
        "id": 1,
        "name": name,
        "plus_one": False,
        "child": False,
        "attending": attending,
        "dietary": "",
        **fields,
    }
