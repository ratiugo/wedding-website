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
"yes" sends, and "test" sends one copy to REPLY_TO. Each send is appended to the
--sent CSV, and those invitations are skipped on later runs.
"""

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from html import escape

import boto3
from botocore.exceptions import ClientError

import card
from load_guests import scan

SITE_URL = os.environ.get("SITE_URL", "")
SENDER = os.environ.get("SENDER", "")
REPLY_TO = os.environ.get("REPLY_TO", "")

AUDIENCES = {
    "accepted": lambda item: any(guest["attending"] for guest in item["guests"]),
    "no-response": lambda item: item["responded_at"] is None,
    "everyone": lambda item: True,
}
HEADERS = ("subject", "audience", "heading", "link")

ses = boto3.client("sesv2")


def main():
    """
    List the recipients, prompt for confirmation, and send.
    """
    parser = argparse.ArgumentParser(description="Email an update to guests.")
    parser.add_argument("message", help="the message file")
    parser.add_argument("--sent", required=True, help="CSV of invitations sent to")
    parser.add_argument("--preview", required=True, help="HTML file for a preview")
    args = parser.parse_args()

    message, problems = read_message(args.message)
    if problems:
        print("The message has problems, so nothing was sent:")
        print("\n".join(f"  {problem}" for problem in problems))
        sys.exit(1)

    table = boto3.resource("dynamodb").Table(os.environ["INVITATIONS_TABLE"])
    to_send, skipped = recipients(scan(table), message["audience"], sent(args.sent))
    print(
        f'{table.name}: "{message["subject"]}" to {len(to_send)} invitations'
        f' ({message["audience"]})'
    )
    print(f"  skipped: {', '.join(f'{n} {why}' for why, n in skipped.items())}")
    if not to_send:
        print("Nobody to send to.")
        return

    with open(args.preview, "w", encoding="utf-8") as file:
        file.write(html(message, to_send[0]))
    print(f"  preview (as {to_send[0]['label']} gets it): {args.preview}")

    while True:
        answer = input(
            f"\nSend? Type yes to send, test to send one copy to {REPLY_TO},"
            " or anything else to stop: "
        ).strip()
        if answer == "test":
            send(message, to_send[0], to=REPLY_TO)
            print(f"Sent a test to {REPLY_TO}.")
        elif answer == "yes":
            break
        else:
            print("Nothing was sent.")
            return

    failed = send_all(message, to_send, args.sent)
    print(f"Sent to {len(to_send) - len(failed)} of {len(to_send)} invitations.")
    if failed:
        print("Failed (run it again to retry them):")
        print("\n".join(f"  {problem}" for problem in failed))


def read_message(path):
    """
    Parse a message file. Return (message, problems).

    message has "subject", "audience" and "paragraphs", plus "heading" and "link"
    (a (text, url) tuple) when given.
    """
    with open(path, encoding="utf-8") as file:
        headers, _, body = file.read().strip().partition("\n\n")

    message = {"paragraphs": [p.strip() for p in re.split(r"\n\s*\n", body) if p]}
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


def recipients(items, audience, already_sent):
    """
    Return (to_send, skipped): the audience's invitations to send to, sorted by
    label, and the number skipped for each reason.
    """
    to_send = []
    skipped = {"without an email": 0, "opted out": 0, "already sent": 0}
    for item in sorted(items, key=lambda item: item["label"]):
        if not AUDIENCES[audience](item):
            continue
        if not item.get("email"):
            skipped["without an email"] += 1
        elif item.get("updates_opt_out"):
            skipped["opted out"] += 1
        elif item["invite_code"] in already_sent:
            skipped["already sent"] += 1
        else:
            to_send.append(item)
    return to_send, skipped


def sent(path):
    """
    Return the invite codes recorded in a sent CSV.
    """
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8", newline="") as file:
        return {row["invite_code"] for row in csv.DictReader(file)}


def send_all(message, items, sent_path):
    """
    Send the update to each invitation, appending each success to the sent CSV.
    Return a description of each failure.
    """
    failed = []
    new_file = not os.path.exists(sent_path)
    with open(sent_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["invite_code", "email", "sent_at"])
        for item in items:
            try:
                send(message, item)
            except ClientError as error:
                failed.append(f"{item['label']} <{item['email']}>: {error}")
                continue
            writer.writerow(
                [item["invite_code"], item["email"], datetime.now(timezone.utc)]
            )
            file.flush()
            # Stay within the SES sandbox limit of one email per second.
            time.sleep(1)
    return failed


def send(message, item, to=None):
    """
    Send the update for an invitation to its email, or to `to` as a test.

    Replies and bounce notifications go to REPLY_TO. The List-Unsubscribe header
    points to the invitation's opt-out page.
    """
    ses.send_email(
        FromEmailAddress=SENDER,
        Destination={"ToAddresses": [to or item["email"]]},
        ReplyToAddresses=[REPLY_TO],
        FeedbackForwardingEmailAddress=REPLY_TO,
        Content={
            "Simple": {
                "Subject": {
                    "Data": ("[Test] " if to else "") + message["subject"],
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {"Data": text(message, item), "Charset": "UTF-8"},
                    "Html": {"Data": html(message, item), "Charset": "UTF-8"},
                },
                "Headers": [
                    {"Name": "List-Unsubscribe", "Value": f"<{opt_out_url(item)}>"}
                ],
            }
        },
    )


def html(message, item):
    """
    Render the update as HTML for an invitation.
    """
    greeting = f"Hi {card.ampersand(escape(item['label']))},"
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
            f'<a href="{escape(opt_out_url(item))}" style="color: inherit;">'
            "Stop getting updates</a>"
        ),
    )


def text(message, item):
    """
    Render the update as plain text for an invitation.
    """
    lines = [f"Hi {item['label']},", *message["paragraphs"]]
    if "link" in message:
        link_text, url = message["link"]
        lines.append(f"{link_text}: {site_url(url)}")
    lines.append(f"--\nStop getting updates: {opt_out_url(item)}")
    return "\n\n".join(lines)


def site_url(url):
    """
    Resolve a message link, prefixing a site-relative path with SITE_URL.
    """
    return SITE_URL + url if url.startswith("/") else url


def opt_out_url(item):
    """
    Return the URL of the invitation's opt-out page.
    """
    return f"{SITE_URL}/opt-out?invite_code={item['invite_code']}"


if __name__ == "__main__":
    main()
