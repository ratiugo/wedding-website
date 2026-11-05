"""
Shared pieces of our emails: HTML building blocks styled to match the save-the-date
card, guest details, and sending through SES.

Styles are inline since most email clients strip <style> blocks. Clients that don't
load web fonts (e.g. Gmail) fall back to Georgia and Arial. Arguments are HTML unless
a function says otherwise, so callers must escape untrusted text.
"""

from html import escape

import boto3

SERIF = "'Cormorant Garamond', Georgia, serif"
SANS = "Jost, 'Helvetica Neue', Arial, sans-serif"
INK = "#3e3a36"
MUTED = "#7a736b"
SAGE = "#9aab8a"
SAGE_DEEP = "#6c7d5e"
LILAC_DEEP = "#9a84b5"

ses = boto3.client("sesv2")

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;1,400&family=Jost&display=swap" rel="stylesheet">
</head>
<body style="margin: 0; padding: 0; background: #efe9f1;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: #efe9f1;">
<tr><td align="center" style="padding: 32px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 560px; background: #fbf9f4; border: 1px solid {sage};">
  <tr><td style="padding: 8px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border: 1px solid {sage};">
    <tr><td align="center" style="padding: 40px 28px; font-family: {serif}; color: {ink};">
      {content}
    </td></tr>
    </table>
  </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""


def card(content, eyebrow="", title="", subtitle="", footer=""):
    """
    Return a complete HTML email. The eyebrow, title, subtitle and footer are
    optional, and a divider follows the title or subtitle.
    """
    parts = []
    if eyebrow:
        parts.append(
            f'<p style="margin: 0; font-family: {SANS}; font-size: 11px;'
            " letter-spacing: 3px; text-transform: uppercase;"
            f' color: {SAGE_DEEP};">{eyebrow}</p>'
        )
    if title:
        parts.append(
            f'<h1 style="margin: 12px 0 4px; font-family: {SERIF}; font-size: 34px;'
            f' font-weight: normal; line-height: 1.2;">{title}</h1>'
        )
    if subtitle:
        parts.append(
            '<p style="margin: 0; font-size: 18px; font-style: italic;'
            f' color: {MUTED};">{subtitle}</p>'
        )
    if title or subtitle:
        parts.append(
            '<hr style="width: 64px; margin: 28px auto; border: 0;'
            f' border-top: 1px solid {SAGE};">'
        )
    parts.append(content)
    if footer:
        parts.append(
            f'<p style="margin: 32px 0 0; font-family: {SANS}; font-size: 11px;'
            f' letter-spacing: 1px; color: {MUTED};">{footer}</p>'
        )
    return PAGE.format(sage=SAGE, serif=SERIF, ink=INK, content="\n".join(parts))


def heading(text):
    """
    Return a small-caps section heading.
    """
    return (
        f'<p style="margin: 24px 0 8px; font-family: {SANS}; font-size: 11px;'
        f' letter-spacing: 3px; text-transform: uppercase; color: {SAGE_DEEP};">'
        f"{text}</p>"
    )


def paragraph(text, space=4):
    """
    Return a body paragraph with `space` pixels of vertical margin.
    """
    return (
        f'<p style="margin: {space}px 0; font-size: 18px; line-height: 1.5;">{text}</p>'
    )


def quote(text):
    """
    Return text as a lilac italic quotation.
    """
    return (
        '<p style="margin: 8px 0 0; font-size: 20px; font-style: italic;'
        f' color: {LILAC_DEEP};">&ldquo;{text}&rdquo;</p>'
    )


def button(text, url):
    """
    Return a link styled as a button.
    """
    return (
        '<p style="margin: 28px 0 0;">'
        f'<a href="{url}" style="display: inline-block; padding: 12px 26px;'
        f" font-family: {SANS}; font-size: 12px; letter-spacing: 2px;"
        " text-transform: uppercase; color: #ffffff; text-decoration: none;"
        f' background: {SAGE_DEEP}; border-radius: 999px;">{text}</a></p>'
    )


def ampersand(text):
    """
    Style each ampersand in already-escaped text (as &amp;) in lilac italics.
    """
    return text.replace(
        "&amp;", f'<span style="font-style: italic; color: {LILAC_DEEP};">&amp;</span>'
    )


def section(title, lines):
    """
    Return a titled list, like "Coming (2)" and a line per guest. The title and
    lines are plain text, and are escaped here.
    """
    return heading(escape(title)) + "".join(paragraph(escape(line)) for line in lines)


def details(guest):
    """
    Return the extras for a guest who is coming, like " (child, dietary: Vegan)".
    """
    extras = ["child"] if guest["child"] else []
    if guest["dietary"]:
        extras.append(f"dietary: {guest['dietary']}")
    return f" ({', '.join(extras)})" if extras else ""


def send(sender, to, subject, text, html, *, reply_to=None, headers=()):
    """
    Send an email through SES, with plain-text and HTML bodies, to the list of
    addresses `to`. Replies and bounce notifications go to reply_to, if given.
    headers are extra headers, like [{"Name": ..., "Value": ...}].
    """
    content = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {
            "Text": {"Data": text, "Charset": "UTF-8"},
            "Html": {"Data": html, "Charset": "UTF-8"},
        },
    }
    if headers:
        content["Headers"] = list(headers)
    reply = (
        {"ReplyToAddresses": [reply_to], "FeedbackForwardingEmailAddress": reply_to}
        if reply_to
        else {}
    )
    ses.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": to},
        Content={"Simple": content},
        **reply,
    )
