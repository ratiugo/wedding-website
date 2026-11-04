"""
The HTML for our emails, styled like the save-the-date card: a cream card with a
double sage border on a lilac background.

Styles are inline, because email apps ignore most stylesheets. Gmail doesn't load
web fonts, so it shows Georgia and Arial instead of Cormorant Garamond and Jost.
Every argument is HTML, so text from guests must be escaped first.
"""

SERIF = "'Cormorant Garamond', Georgia, serif"
SANS = "Jost, 'Helvetica Neue', Arial, sans-serif"
INK = "#3e3a36"
MUTED = "#7a736b"
SAGE = "#9aab8a"
SAGE_DEEP = "#6c7d5e"
LILAC_DEEP = "#9a84b5"

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
    A whole email: an optional small-caps eyebrow, title and italic subtitle, a rule
    under them, then the content and an optional small footer.
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
    A small-caps heading for a section, like "Coming (2)".
    """
    return (
        f'<p style="margin: 24px 0 8px; font-family: {SANS}; font-size: 11px;'
        f' letter-spacing: 3px; text-transform: uppercase; color: {SAGE_DEEP};">'
        f"{text}</p>"
    )


def paragraph(text, space=4):
    """
    A paragraph of body text, with space pixels above and below: a little for lines
    in a list, more for paragraphs of a message.
    """
    return (
        f'<p style="margin: {space}px 0; font-size: 18px; line-height: 1.5;">{text}</p>'
    )


def quote(text):
    """
    Text in lilac italics between curly quotes, like a guest's note.
    """
    return (
        '<p style="margin: 8px 0 0; font-size: 20px; font-style: italic;'
        f' color: {LILAC_DEEP};">&ldquo;{text}&rdquo;</p>'
    )


def button(text, url):
    """
    A rounded sage link styled as a button.
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
    Text with its ampersands in lilac italics, as on the save-the-date. The text
    must already be escaped, so its ampersands are &amp;.
    """
    return text.replace(
        "&amp;", f'<span style="font-style: italic; color: {LILAC_DEEP};">&amp;</span>'
    )
