"""
Sending our emails through SES.
"""

import boto3

ses = boto3.client("sesv2")


def content(subject, text, html, headers=()):
    """
    Return an email's subject, plain-text and HTML bodies, and any extra headers
    (like [{"Name": ..., "Value": ...}]) as SES's Content.
    """
    simple = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {
            "Text": {"Data": text, "Charset": "UTF-8"},
            "Html": {"Data": html, "Charset": "UTF-8"},
        },
    }
    if headers:
        simple["Headers"] = list(headers)
    return {"Simple": simple}


def send(sender, to, email_content, reply_to=None):
    """
    Send an email through SES to the list of addresses `to`. Replies and bounce
    notifications go to reply_to, if given.
    """
    reply = (
        {"ReplyToAddresses": [reply_to], "FeedbackForwardingEmailAddress": reply_to}
        if reply_to
        else {}
    )
    ses.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": to},
        Content=email_content,
        **reply,
    )
