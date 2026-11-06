"""
Shared pieces of emails: HTML building blocks styled to match the website (text on
a translucent panel over a photo, thin typewriter capitals for labels, light
sans-serif text), and guest details.

Styles are inline since most email clients strip <style> blocks. Clients that don't
load web fonts (e.g. Gmail) fall back to Menlo or Consolas, and Helvetica or Arial.
Arguments are HTML unless a function says otherwise, so callers must escape untrusted
text.
"""

from html import escape

MONO = "Inconsolata, Menlo, Consolas, 'Courier New', monospace"
SANS = "Poppins, 'Helvetica Neue', Helvetica, Arial, sans-serif"
INK = "#4a4947"
TEXT = "#6b6a68"
MUTED = "#959594"
TAUPE = "#cfc7c0"

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inconsolata:wght@300&family=Poppins:wght@200;300&display=swap" rel="stylesheet">
</head>
<body style="margin: 0; padding: 0; background: #ffffff;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background: #ffffff;">
<tr><td align="center" {backdrop}>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 560px;">
  <tr><td align="center" {panel}>
    {content}
  </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""

# With a photo, it fills the background and the text sits on a translucent white
# panel over it. The grey under the photo keeps the panel readable in email apps that
# don't show background images (like Outlook on Windows) or block images until asked.
PHOTO_BACKDROP = (
    'background="{url}" style="padding: 72px 16px; background: #8f8b86 url(\'{url}\')'
    ' center / cover no-repeat;"'
)
PHOTO_PANEL = (
    'style="padding: 44px 32px; background: #ffffff; background: rgba(255, 255, 255,'
    ' .9); font-family: {sans}; font-weight: 300; color: {text};"'
)
PLAIN_BACKDROP = 'style="padding: 48px 20px 56px;"'
PLAIN_PANEL = 'style="font-family: {sans}; font-weight: 300; color: {text};"'


def card(content, title="", subtitle="", footer="", photo=""):
    """
    Return a complete HTML email, headed by our names. The title, subtitle and
    footer are optional, and a divider follows the title or subtitle. photo is the
    URL of an image for the background, if any.
    """
    parts = [
        f'<p style="margin: 0; font-family: {MONO}; font-size: 13px;'
        " letter-spacing: 2px; text-transform: uppercase;"
        f' color: {MUTED};">Tess + Colton</p>'
    ]
    if title:
        parts.append(
            f'<h1 style="margin: 14px 0 6px; font-family: {SANS}; font-size: 30px;'
            " font-weight: 200; letter-spacing: 1px; text-transform: uppercase;"
            f' line-height: 1.2; color: {MUTED};">{title}</h1>'
        )
    if subtitle:
        parts.append(
            f'<p style="margin: 0; font-family: {MONO}; font-size: 14px;'
            f' letter-spacing: 2px; text-transform: uppercase; color: {TEXT};">'
            f"{subtitle}</p>"
        )
    if title or subtitle:
        parts.append(
            '<hr style="width: 48px; margin: 28px auto; border: 0;'
            f' border-top: 1px solid {TAUPE};">'
        )
    parts.append(content)
    if footer:
        parts.append(
            f'<p style="margin: 36px 0 0; font-family: {MONO}; font-size: 12px;'
            f' letter-spacing: 1px; color: {MUTED};">{footer}</p>'
        )
    backdrop = PHOTO_BACKDROP.format(url=photo) if photo else PLAIN_BACKDROP
    panel = (PHOTO_PANEL if photo else PLAIN_PANEL).format(sans=SANS, text=TEXT)
    return PAGE.format(backdrop=backdrop, panel=panel, content="\n".join(parts))


def heading(text):
    """
    Return a section heading in spaced capitals.
    """
    return (
        f'<p style="margin: 26px 0 8px; font-family: {MONO}; font-size: 13px;'
        f' letter-spacing: 3px; text-transform: uppercase; color: {INK};">'
        f"{text}</p>"
    )


def paragraph(text, space=4):
    """
    Return a body paragraph with `space` pixels of vertical margin.
    """
    return (
        f'<p style="margin: {space}px 0; font-size: 16px; line-height: 1.7;">{text}</p>'
    )


def quote(text):
    """
    Return text as an italic quotation.
    """
    return (
        '<p style="margin: 12px 0 0; font-size: 17px; font-style: italic;'
        f' color: {MUTED};">&ldquo;{text}&rdquo;</p>'
    )


def button(text, url):
    """
    Return a link styled as an outlined button.
    """
    return (
        '<p style="margin: 30px 0 0;">'
        f'<a href="{url}" style="display: inline-block; padding: 13px 30px;'
        f" font-family: {MONO}; font-size: 13px; letter-spacing: 3px;"
        f" text-transform: uppercase; color: {INK}; text-decoration: none;"
        f' border: 1px solid {TAUPE};">{text}</a></p>'
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
