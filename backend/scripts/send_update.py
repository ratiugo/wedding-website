"""
Send an update email to the invitations in DynamoDB.

Usage: make send-update FILE=updates/<name>.txt [ENV=prod]

A message file is headers, a blank line, then the body. Paragraphs are separated by
blank lines.

    Subject: The weekend itinerary is up
    Audience: accepted
    Heading: The weekend
    Link: See the itinerary | /itinerary

    We've added the full schedule for the weekend.

Headers:
    Subject   Required.
    Audience  Required: accepted (at least one guest attending), no-response (no
              RSVP yet) or everyone.
    Heading   Optional title.
    Link      Optional button, as "text | url". A url starting with / is relative to
              SITE_URL.

Invitations without an email, or with updates_opt_out set, are skipped. Before
sending, the script lists the recipients, writes an HTML preview, and prompts:
"yes" sends, and "test" sends one copy to REPLY_TO.

The update's name is the message file's name without .txt. After each send, it's
added to the invitation's updates_sent set, and invitations that already have it
are skipped, so a rerun only sends to the rest.
"""

import argparse
import os
import re
import sys
import time
from collections import Counter
from html import escape
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

import card
from load_guests import get_invitations

SITE_URL = os.environ.get("SITE_URL", "")
SENDER = os.environ.get("SENDER", "")
REPLY_TO = os.environ.get("REPLY_TO", "")

AUDIENCES = ("accepted", "no-response", "everyone")
HEADERS = ("subject", "audience", "heading", "link")

ses = boto3.client("sesv2")


def main():
    """
    Validate the message, choose its recipients, confirm, and send.
    """
    parser = argparse.ArgumentParser(description="Email an update to guests.")
    parser.add_argument("message", help="the message file")
    parser.add_argument("--preview", required=True, help="HTML file for a preview")
    args = parser.parse_args()

    message, problems = read_message(args.message)
    if problems:
        print("The message has problems, so nothing was sent:")
        print("\n".join(f"  {problem}" for problem in problems))
        sys.exit(1)

    table = boto3.resource("dynamodb").Table(os.environ["INVITATIONS_TABLE"])
    invitations = get_invitations(table)
    recipients, skipped = get_recipients(invitations, message)
    print_plan(table.name, message, recipients, skipped)
    if not recipients:
        return

    with open(args.preview, "w", encoding="utf-8") as file:
        file.write(html(message, recipients[0]))
    print(f"  preview (as {recipients[0]['label']} gets it): {args.preview}")

    if confirm_send(message, recipients[0]):
        failed = send_to_recipients(table, message, recipients)
        print(f"Sent to {len(recipients) - len(failed)} of {len(recipients)}.")
        if failed:
            print("Failed (run it again to retry them):")
            print("\n".join(f"  {failure}" for failure in failed))


def read_message(path):
    """
    Parse a message file. Return (message, problems).

    message has "name" (the file's name without .txt), "subject", "audience" and
    "paragraphs", plus "heading" and "link" (a (text, url) tuple) when given.
    """
    with open(path, encoding="utf-8") as file:
        headers, _, body = file.read().strip().partition("\n\n")

    message = {
        "name": Path(path).stem,
        "paragraphs": [p.strip() for p in re.split(r"\n\s*\n", body) if p],
    }
    problems = []
    for line in headers.splitlines():
        name, _, value = line.partition(":")
        if name.strip().lower() in HEADERS:
            message[name.strip().lower()] = value.strip()
        else:
            problems.append(f"Unknown header: {line}")

    for header in ("subject", "audience"):
        if not message.get(header):
            problems.append(f"Missing header: {header.capitalize()}")
    if message.get("audience") and message["audience"] not in AUDIENCES:
        problems.append(f"Audience should be one of: {', '.join(AUDIENCES)}")
    if "link" in message:
        link_text, _, url = message["link"].partition("|")
        if not link_text.strip() or not url.strip():
            problems.append("Link should be like: See the itinerary | /itinerary")
        message["link"] = (link_text.strip(), url.strip())
    if not message["paragraphs"]:
        problems.append("The message is empty")
    return message, problems


def get_recipients(invitations, message):
    """
    Return (recipients, skipped): the invitations in the message's audience that can
    be sent to, sorted by label, and the number skipped for each reason.
    """
    recipients = []
    skipped = Counter()
    for invitation in sorted(invitations, key=lambda invitation: invitation["label"]):
        if not in_audience(invitation, message["audience"]):
            continue
        reason = skip_reason(invitation, message["name"])
        if reason:
            skipped[reason] += 1
        else:
            recipients.append(invitation)
    return recipients, skipped


def in_audience(invitation, audience):
    """
    Whether an invitation is in the audience.
    """
    if audience == "accepted":
        return any(guest["attending"] for guest in invitation["guests"])
    if audience == "no-response":
        return invitation["responded_at"] is None
    return True


def skip_reason(invitation, update_name):
    """
    Why an invitation can't be sent the update, or None if it can.
    """
    if not invitation.get("email"):
        return "no email"
    if invitation.get("updates_opt_out"):
        return "opted out"
    if update_name in invitation.get("updates_sent", set()):
        return "already sent"
    return None


def print_plan(table_name, message, recipients, skipped):
    """
    Print who the update would be sent to, and how many were skipped and why.
    """
    print(
        f'{table_name}: "{message["subject"]}" to {len(recipients)} invitations'
        f' ({message["audience"]})'
    )
    reasons = ", ".join(f"{count} {reason}" for reason, count in skipped.items())
    print(f"  skipped: {reasons or 'none'}")
    if not recipients:
        print("Nobody to send to.")


def confirm_send(message, sample):
    """
    Prompt until the user sends or stops. "test" sends the sample invitation's
    email to REPLY_TO and prompts again. Return whether to send.
    """
    while True:
        answer = input(
            f"\nSend? Type yes to send, test to send one copy to {REPLY_TO},"
            " or anything else to stop: "
        ).strip()
        if answer == "yes":
            return True
        if answer != "test":
            print("Nothing was sent.")
            return False
        send(message, sample, to=REPLY_TO)
        print(f"Sent a test to {REPLY_TO}.")


def send_to_recipients(table, message, recipients):
    """
    Send the update to each recipient, adding it to the invitation's updates_sent
    after each success. Return a description of each failure.
    """
    failed = []
    for invitation in recipients:
        try:
            send(message, invitation)
        except ClientError as error:
            failed.append(f"{invitation['label']} <{invitation['email']}>: {error}")
            continue
        table.update_item(
            Key={"invite_code": invitation["invite_code"]},
            UpdateExpression="ADD updates_sent :name",
            ExpressionAttributeValues={":name": {message["name"]}},
        )
        # Stay within the SES sandbox limit of one email per second.
        time.sleep(1)
    return failed


def send(message, invitation, to=None):
    """
    Send the update for an invitation to its email, or to `to` as a test.

    Replies and bounce notifications go to REPLY_TO. The List-Unsubscribe header
    points to the invitation's opt-out page.
    """
    ses.send_email(
        FromEmailAddress=SENDER,
        Destination={"ToAddresses": [to or invitation["email"]]},
        ReplyToAddresses=[REPLY_TO],
        FeedbackForwardingEmailAddress=REPLY_TO,
        Content={
            "Simple": {
                "Subject": {
                    "Data": ("[Test] " if to else "") + message["subject"],
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {"Data": text(message, invitation), "Charset": "UTF-8"},
                    "Html": {"Data": html(message, invitation), "Charset": "UTF-8"},
                },
                "Headers": [
                    {
                        "Name": "List-Unsubscribe",
                        "Value": f"<{opt_out_url(invitation)}>",
                    }
                ],
            }
        },
    )


def html(message, invitation):
    """
    Render the update as HTML for an invitation.
    """
    greeting = f"Hi {card.ampersand(escape(invitation['label']))},"
    content = [card.paragraph(greeting, space=14)]
    content += [
        card.paragraph(escape(paragraph).replace("\n", "<br>"), space=14)
        for paragraph in message["paragraphs"]
    ]
    if "link" in message:
        link_text, url = message["link"]
        content.append(card.button(escape(link_text), escape(site_url(url))))
    return card.card(
        "\n".join(content),
        eyebrow=card.ampersand("Tess &amp; Colton"),
        title=card.ampersand(escape(message.get("heading", ""))),
        footer=(
            "You're getting this because you're invited to our wedding. "
            f'<a href="{escape(opt_out_url(invitation))}" style="color: inherit;">'
            "Stop getting updates</a>"
        ),
    )


def text(message, invitation):
    """
    Render the update as plain text for an invitation.
    """
    lines = [f"Hi {invitation['label']},", *message["paragraphs"]]
    if "link" in message:
        link_text, url = message["link"]
        lines.append(f"{link_text}: {site_url(url)}")
    lines.append(f"--\nStop getting updates: {opt_out_url(invitation)}")
    return "\n\n".join(lines)


def site_url(url):
    """
    Resolve a message link, prefixing a site-relative path with SITE_URL.
    """
    return SITE_URL + url if url.startswith("/") else url


def opt_out_url(invitation):
    """
    Return the URL of the invitation's opt-out page.
    """
    return f"{SITE_URL}/opt-out?invite_code={invitation['invite_code']}"


if __name__ == "__main__":
    main()
