"""Email bodies: one light layout that survives Gmail, Outlook and Apple Mail, plus a plain-text twin.

Email clients strip <style> blocks unevenly and invert dark designs, so everything is inline, built from tables,
on a light background. All user text is escaped.
"""

from dataclasses import dataclass
from html import escape

from app.config import settings

PAGE = "#F4F4F5"
CARD = "#FFFFFF"
SUBTLE = "#FAFAFA"
BORDER = "#E4E4E7"
INK = "#09090B"
TEXT = "#3F3F46"
MUTED = "#71717A"
FAINT = "#A1A1AA"
ACCENT = "#C8F031"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


@dataclass
class Mail:
    subject: str
    html: str
    text: str


def _style(**props: str) -> str:
    return ";".join(f"{k.replace('_', '-')}:{v}" for k, v in props.items())


def _layout(preheader: str, body: str, footer: str = "") -> str:
    logo = f"{settings.app_url}/icon-192.png"
    home = settings.app_url
    footer = footer or "You're getting this because you have a Stash account."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">
<title>Stash</title></head>
<body style="margin:0;padding:0;background-color:{PAGE};-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAGE};">{escape(preheader)}&#8203;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE}"
 style="background-color:{PAGE};">
<tr><td align="center" style="padding:36px 12px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;">
<tr><td style="padding:0 4px 20px;">
  <a href="{escape(home)}" style="text-decoration:none;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
    <td style="padding-right:10px;"><img src="{escape(logo)}" width="32" height="32" alt=""
      style="display:block;width:32px;height:32px;border-radius:8px;border:0;"></td>
    <td style="{_style(font_family=FONT, font_size='17px', font_weight='700', letter_spacing='-0.02em', color=INK)}">
      Stash</td>
  </tr></table></a>
</td></tr>
<tr><td bgcolor="{CARD}" style="{_style(background_color=CARD, border=f'1px solid {BORDER}', border_radius='16px',
    padding='32px 28px', font_family=FONT, font_size='15px', line_height='24px', color=TEXT)}">{body}</td></tr>
<tr><td style="{_style(padding='20px 8px 0', font_family=FONT, font_size='12px', line_height='19px', color=FAINT,
    text_align='center')}">{footer}<br>
  <a href="{escape(home)}" style="color:{FAINT};text-decoration:underline;">Stash</a> &middot; a canvas for everything
  you save</td></tr>
</table></td></tr></table></body></html>"""


def _eyebrow(label: str) -> str:
    style = _style(background_color=ACCENT, border_radius="999px", padding="3px 10px", font_family=FONT,
                   font_size="11px", line_height="16px", font_weight="700", letter_spacing="0.06em",
                   text_transform="uppercase", color=INK)
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 14px;"><tr>'
            f'<td bgcolor="{ACCENT}" style="{style}">{escape(label)}</td></tr></table>')


def _h(text: str) -> str:
    style = _style(margin="0 0 10px", font_family=FONT, font_size="24px", line_height="30px", font_weight="700",
                   letter_spacing="-0.02em", color=INK)
    return f'<h1 style="{style}">{escape(text)}</h1>'


def _p(text: str, color: str = TEXT, margin: str = "0 0 20px", size: str = "15px") -> str:
    return f'<p style="{_style(margin=margin, font_size=size, line_height="24px", color=color)}">{escape(text)}</p>'


def _button(label: str, url: str) -> str:
    """Table-based so Outlook draws the background too."""
    style = _style(display="inline-block", padding="13px 22px", font_family=FONT, font_size="15px",
                   line_height="18px", font_weight="600", color="#FFFFFF", text_decoration="none",
                   border_radius="10px")
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 0;"><tr>'
            f'<td bgcolor="{INK}" style="background-color:{INK};border-radius:10px;">'
            f'<a href="{escape(url)}" style="{style}">{escape(label)} &rarr;</a></td></tr></table>')


def _divider() -> str:
    return f'<div style="height:1px;line-height:1px;background-color:{BORDER};margin:24px 0;">&nbsp;</div>'


def _fallback_link(url: str) -> str:
    return (_divider() + _p("Button not working? Paste this link into your browser:", MUTED, "0 0 6px", "13px")
            + f'<p style="margin:0;font-size:12px;line-height:18px;word-break:break-all;">'
              f'<a href="{escape(url)}" style="color:{MUTED};">{escape(url)}</a></p>')


def _panel(inner: str) -> str:
    style = _style(background_color=SUBTLE, border=f"1px solid {BORDER}", border_left=f"4px solid {ACCENT}",
                   border_radius="12px", padding="16px 18px")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:0 0 24px;"><tr><td bgcolor="{SUBTLE}" style="{style}">{inner}</td></tr></table>')


def _label(text: str) -> str:
    style = _style(font_size="11px", line_height="16px", font_weight="700", letter_spacing="0.06em",
                   text_transform="uppercase", color=MUTED, margin="0 0 10px")
    return f'<div style="{style}">{escape(text)}</div>'


# ---------- account ----------

def verify_email(link: str) -> Mail:
    body = (_eyebrow("Welcome") + _h("Confirm your email")
            + _p("One click and your Stash account is ready. The link works for 24 hours.")
            + _button("Confirm email", link) + _fallback_link(link)
            + _p("If you didn't sign up for Stash, ignore this email and nothing will happen.", FAINT, "16px 0 0",
                 "13px"))
    text = f"Confirm your email\n\nOpen this link to finish setting up Stash (valid 24 hours):\n{link}\n\n" \
           "If you didn't sign up, ignore this email."
    return Mail("Confirm your email for Stash", _layout("One click and your Stash account is ready.", body), text)


def reset_password(link: str) -> Mail:
    body = (_eyebrow("Account") + _h("Reset your password")
            + _p("Choose a new password with the button below. The link works once, for 30 minutes.")
            + _button("Choose a new password", link) + _fallback_link(link)
            + _p("Didn't ask for this? Ignore this email. Your password stays the same.", FAINT, "16px 0 0", "13px"))
    text = f"Reset your password\n\nOpen this link to choose a new password (valid 30 minutes, once):\n{link}\n\n" \
           "If you didn't ask for this, ignore this email."
    return Mail("Reset your Stash password", _layout("Choose a new password for Stash.", body), text)


# ---------- reminders ----------

def reminder(card_title: str, card_snippet: str, note: str, canvas_title: str, link: str) -> Mail:
    """`card_title` is empty for a reminder that isn't on a card."""
    if card_title:
        card = (f'<div style="font-size:12px;line-height:18px;color:{MUTED};margin:0 0 4px;">On '
                f'<strong style="color:{TEXT};">{escape(canvas_title)}</strong></div>'
                f'<div style="font-size:16px;line-height:22px;font-weight:600;color:{INK};">{escape(card_title)}</div>'
                + (f'<div style="font-size:14px;line-height:21px;color:{TEXT};margin-top:6px;">'
                   f"{escape(card_snippet)}</div>" if card_snippet else ""))
        body = (_eyebrow("Reminder") + _h(note or "Time to come back to this")
                + _p("You asked Stash to remind you about this card." if note else
                     "You set a reminder on this card.", MUTED)
                + _panel(card) + _button("Open the card", link))
        headline = note or card_title
    else:
        body = (_eyebrow("Reminder") + _h(note or "Your reminder")
                + _p("You asked Stash to remind you.", MUTED) + _button("Open Stash", link))
        headline = note or "Your reminder"
    text = "Reminder\n\n" + (f"{note}\n\n" if note else "") \
        + (f"{card_title}\n{card_snippet}\nOn: {canvas_title}\n\n" if card_title else "") + f"Open in Stash: {link}"
    return Mail(f"Reminder: {headline}"[:120], _layout(headline, body), text)


# ---------- digests ----------

@dataclass
class DigestSection:
    canvas_title: str
    canvas_link: str
    cards: list[tuple[str, str]]  # (kind label, title)
    more: int


def _chip(text: str) -> str:
    style = _style(display="inline-block", background_color="#F4F4F5", border=f"1px solid {BORDER}",
                   border_radius="6px", padding="1px 7px", font_size="11px", line_height="16px", font_weight="600",
                   color=MUTED)
    return f'<span style="{style}">{escape(text)}</span>'


def digest(kind: str, period_label: str, key_points: list[str], sections: list[DigestSection],
           reminders: list[tuple[str, str]], total: int, unsubscribe_link: str, settings_link: str) -> Mail:
    title = "Your day in Stash" if kind == "daily" else "Your week in Stash"
    noun = "card" if total == 1 else "cards"
    parts = [_eyebrow("Daily digest" if kind == "daily" else "Weekly digest"), _h(title),
             _p(f"{period_label} · {total} {noun} saved", MUTED, "0 0 24px")]

    if key_points:
        rows = "".join(
            f'<tr><td width="18" valign="top" style="padding:0 0 8px;font-size:15px;line-height:22px;color:{INK};">'
            f'&bull;</td><td style="padding:0 0 8px;font-size:14px;line-height:22px;color:{INK};">{escape(point)}'
            f"</td></tr>" for point in key_points)
        parts.append(_panel(_label("Key points") + f'<table role="presentation" cellpadding="0" cellspacing="0" '
                                                   f'border="0" width="100%">{rows}</table>'))

    for i, section in enumerate(sections):
        rows = "".join(
            f'<tr><td width="64" valign="top" style="padding:7px 10px 7px 0;">{_chip(label)}</td>'
            f'<td style="padding:7px 0;font-size:14px;line-height:21px;color:{INK};border-bottom:1px solid #F1F1F3;">'
            f"{escape(card_title)}</td></tr>" for label, card_title in section.cards)
        more = (f'<div style="font-size:13px;line-height:20px;color:{MUTED};padding-top:8px;">'
                f'+ {section.more} more on this canvas</div>' if section.more else "")
        top = "0" if i == 0 and not key_points else "8px"
        link_style = _style(font_size="15px", line_height="22px", font_weight="700", color=INK,
                            text_decoration="none")
        parts.append(
            f'<div style="margin:{top} 0 18px;">'
            f'<a href="{escape(section.canvas_link)}" style="{link_style}">'
            f'{escape(section.canvas_title)} <span style="color:{FAINT};font-weight:400;">&rarr;</span></a>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="margin-top:6px;">{rows}</table>{more}</div>')

    if reminders:
        rows = "".join(
            f'<tr><td width="84" valign="top" style="padding:6px 10px 6px 0;font-size:13px;line-height:20px;'
            f'font-weight:600;color:{INK};white-space:nowrap;">{escape(when)}</td>'
            f'<td style="padding:6px 0;font-size:14px;line-height:20px;color:{TEXT};">{escape(what)}</td></tr>'
            for when, what in reminders)
        heading = "Reminders today" if kind == "daily" else "Reminders this week"
        parts.append(_divider() + _label(heading) + f'<table role="presentation" cellpadding="0" cellspacing="0" '
                                                    f'border="0" width="100%" style="margin:0 0 8px;">{rows}</table>')

    parts.append(f'<div style="margin-top:20px;">{_button("Open Stash", f"{settings.app_url}/app")}</div>')
    footer = (f'You get this because {kind} digests are on. <a href="{escape(settings_link)}" '
              f'style="color:{MUTED};text-decoration:underline;">Email settings</a> &middot; '
              f'<a href="{escape(unsubscribe_link)}" style="color:{MUTED};text-decoration:underline;">'
              f"Unsubscribe from {kind} digests</a>")

    lines = [title, f"{period_label} · {total} {noun} saved", ""]
    if key_points:
        lines += ["Key points:"] + [f"- {p}" for p in key_points] + [""]
    for section in sections:
        lines.append(section.canvas_title)
        lines += [f"  [{label}] {card_title}" for label, card_title in section.cards]
        if section.more:
            lines.append(f"  and {section.more} more")
        lines.append("")
    if reminders:
        lines += ["Reminders:"] + [f"- {when}: {what}" for when, what in reminders] + [""]
    lines.append(f"Unsubscribe from {kind} digests: {unsubscribe_link}")
    return Mail(f"{title}: {total} {noun} saved", _layout(f"{total} {noun} saved. Here's what stood out.",
                                                          "".join(parts), footer), "\n".join(lines))
