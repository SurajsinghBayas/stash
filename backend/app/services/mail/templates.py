"""Email bodies: one HTML layout in the Graphite palette plus a plain-text twin. All user text is escaped."""

from dataclasses import dataclass
from html import escape

BG = "#09090B"
SURFACE = "#141416"
BORDER = "#26262B"
TEXT = "#EDEDEF"
MUTED = "#A1A1AA"
FAINT = "#68686F"
ACCENT = "#C8F031"
ACCENT_FG = "#09090B"


@dataclass
class Mail:
    subject: str
    html: str
    text: str


def _layout(preheader: str, body: str, footer: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="dark"><title>Stash</title></head>
<body style="margin:0;padding:0;background:{BG};">
<span style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">
<tr><td style="padding:0 4px 20px;font:600 17px/1 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:{TEXT};">
<span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:{ACCENT};
margin-right:8px;"></span>Stash
</td></tr>
<tr><td style="background:{SURFACE};border:1px solid {BORDER};border-radius:16px;padding:28px;
font:400 15px/1.6 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:{TEXT};">{body}</td></tr>
<tr><td style="padding:18px 4px;font:400 12px/1.6 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:{FAINT};">
{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _button(label: str, url: str) -> str:
    return (f'<a href="{escape(url)}" style="display:inline-block;background:{ACCENT};color:{ACCENT_FG};'
            f'font-weight:600;text-decoration:none;padding:12px 20px;border-radius:10px;">{escape(label)}</a>')


def _h(text: str) -> str:
    style = f"margin:0 0 12px;font-size:22px;line-height:1.3;font-weight:600;color:{TEXT};"
    return f'<h1 style="{style}">{escape(text)}</h1>'


def _p(text: str, color: str = MUTED) -> str:
    return f'<p style="margin:0 0 16px;color:{color};">{escape(text)}</p>'


def verify_email(link: str) -> Mail:
    body = (_h("Confirm your email") + _p("Click the button to finish setting up your Stash account. "
            "The link works for 24 hours.") + _button("Confirm email", link)
            + _p("If you didn't sign up for Stash, you can ignore this email.", FAINT).replace(
                "margin:0 0 16px", "margin:20px 0 0"))
    text = f"Confirm your email\n\nOpen this link to finish setting up Stash (valid 24 hours):\n{link}\n\n" \
           "If you didn't sign up, ignore this email."
    return Mail("Confirm your email for Stash", _layout("Finish setting up Stash", body), text)


def reset_password(link: str) -> Mail:
    body = (_h("Reset your password") + _p("Click the button to choose a new password. "
            "The link works once, for 30 minutes.") + _button("Choose a new password", link)
            + _p("If you didn't ask for this, you can ignore this email. Your password stays the same.",
                 FAINT).replace("margin:0 0 16px", "margin:20px 0 0"))
    text = f"Reset your password\n\nOpen this link to choose a new password (valid 30 minutes, once):\n{link}\n\n" \
           "If you didn't ask for this, ignore this email."
    return Mail("Reset your Stash password", _layout("Choose a new password", body), text)


def reminder(card_title: str, card_snippet: str, note: str, canvas_title: str, link: str) -> Mail:
    note_html = (f'<p style="margin:0 0 16px;color:{TEXT};font-size:16px;">{escape(note)}</p>' if note else "")
    card_html = (
        f'<div style="border:1px solid {BORDER};border-radius:12px;padding:14px 16px;margin:0 0 20px;">'
        f'<div style="font-size:12px;color:{FAINT};margin-bottom:4px;">{escape(canvas_title)}</div>'
        f'<div style="font-weight:600;color:{TEXT};">{escape(card_title)}</div>'
        + (f'<div style="color:{MUTED};font-size:14px;margin-top:4px;">{escape(card_snippet)}</div>'
           if card_snippet else "")
        + "</div>"
    )
    body = _h("Reminder") + note_html + card_html + _button("Open in Stash", link)
    text = "Reminder\n\n" + (f"{note}\n\n" if note else "") + f"{card_title}\n{card_snippet}\n" \
           f"On: {canvas_title}\n\nOpen in Stash: {link}"
    subject = f"Reminder: {note or card_title}"[:120]
    return Mail(subject, _layout(note or card_title, body), text)


@dataclass
class DigestSection:
    canvas_title: str
    canvas_link: str
    cards: list[tuple[str, str]]  # (kind label, title)
    more: int


def digest(kind: str, period_label: str, key_points: list[str], sections: list[DigestSection],
           reminders: list[tuple[str, str]], total: int, unsubscribe_link: str, settings_link: str) -> Mail:
    title = "Your day in Stash" if kind == "daily" else "Your week in Stash"
    noun = "card" if total == 1 else "cards"
    parts = [_h(title), _p(f"{period_label} · {total} {noun} noted")]
    if key_points:
        items = "".join(f'<li style="margin:0 0 6px;">{escape(point)}</li>' for point in key_points)
        parts.append(f'<div style="font-size:12px;color:{FAINT};text-transform:uppercase;letter-spacing:.06em;'
                     f'margin:8px 0 8px;">Key points</div><ul style="margin:0 0 20px;padding-left:20px;color:{TEXT};">'
                     f"{items}</ul>")
    for section in sections:
        rows = "".join(
            f'<tr><td style="padding:6px 0;color:{FAINT};font-size:12px;width:56px;vertical-align:top;">'
            f'{escape(label)}</td><td style="padding:6px 0;color:{TEXT};font-size:14px;">{escape(card_title)}</td></tr>'
            for label, card_title in section.cards
        )
        more = (f'<div style="color:{FAINT};font-size:13px;padding-top:4px;">and {section.more} more</div>'
                if section.more else "")
        parts.append(
            f'<div style="border-top:1px solid {BORDER};padding-top:14px;margin-top:6px;">'
            f'<a href="{escape(section.canvas_link)}" style="color:{TEXT};font-weight:600;text-decoration:none;">'
            f'{escape(section.canvas_title)}</a><table role="presentation" width="100%" style="margin-top:6px;">'
            f"{rows}</table>{more}</div>"
        )
    if reminders:
        rows = "".join(f'<li style="margin:0 0 6px;"><span style="color:{FAINT};">{escape(when)}</span> · '
                       f"{escape(what)}</li>" for when, what in reminders)
        heading = "Reminders today" if kind == "daily" else "Reminders this week"
        parts.append(f'<div style="border-top:1px solid {BORDER};padding-top:14px;margin-top:14px;font-weight:600;">'
                     f'{heading}</div><ul style="margin:8px 0 0;padding-left:20px;color:{TEXT};">{rows}</ul>')
    footer = (f'You get this because {kind} digests are on. <a href="{escape(settings_link)}" '
              f'style="color:{MUTED};">Email settings</a> · <a href="{escape(unsubscribe_link)}" '
              f'style="color:{MUTED};">Unsubscribe from {kind} digests</a>')

    lines = [title, f"{period_label} · {total} {noun} noted", ""]
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
    return Mail(f"{title}: {total} {noun} noted", _layout(f"{total} {noun} noted", "".join(parts), footer),
                "\n".join(lines))
