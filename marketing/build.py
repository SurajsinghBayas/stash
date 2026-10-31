# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.40", "fonttools>=4.40", "brotli>=1.1", "numpy>=1.26"]
# ///
"""Builds the Stash ad kit: `uv run marketing/build.py` from the repo root (needs Google Chrome and ffmpeg).

Writes marketing/ads/{svg,png,video}/ and the link-preview banner frontend/public/og.{svg,png}.
Every creative is generated from the components below, so copy or colour changes happen in one place.
Text is measured with the real Geist font so wrapping is exact, and the font is embedded in every SVG.
"""

import base64
import html
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FONT_DIR = REPO / "frontend/node_modules/@fontsource-variable"
SANS_FILE = FONT_DIR / "geist/files/geist-latin-wght-normal.woff2"
MONO_FILE = FONT_DIR / "geist-mono/files/geist-mono-latin-wght-normal.woff2"
OUT = ROOT / "ads"
URL = "stash.surajbayas.me"

# ---------- brand ----------
BG = "#09090B"
CANVAS = "#0C0C0E"
SURF = "#121214"
SURF2 = "#1A1A1D"
SURF3 = "#232327"
BORDER = "#26262B"
BORDER2 = "#34343A"
TEXT = "#EDEDEF"
TEXT2 = "#A1A1AA"
TEXT3 = "#68686F"
ACCENT = "#C8F031"
NOTE = {"yellow": ("#2A2614", "#F5E7A1"), "blue": ("#141D2B", "#BCD4F5"), "green": ("#142219", "#BFE6CB"),
        "pink": ("#2A161C", "#F3C5D1")}
SANS = "Geist, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'Geist Mono', ui-monospace, Menlo, monospace"


# ---------- text measuring ----------

class Metrics:
    """Advance widths from the real font, per weight (Geist is a variable font)."""

    def __init__(self, path: Path):
        self.path = path
        self.fonts: dict[int, tuple[dict, dict, int]] = {}

    def _font(self, weight: int):
        if weight not in self.fonts:
            font = instancer.instantiateVariableFont(TTFont(self.path), {"wght": weight})
            self.fonts[weight] = (font.getBestCmap(), font["hmtx"].metrics, font["head"].unitsPerEm)
        return self.fonts[weight]

    def width(self, text: str, size: float, weight: int = 400, spacing: float = 0) -> float:
        cmap, hmtx, upem = self._font(weight)
        units = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text)
        return units * size / upem + spacing * max(0, len(text) - 1)


SANS_M = Metrics(SANS_FILE)
MONO_M = Metrics(MONO_FILE)


def wrap(text: str, size: float, weight: int, max_w: float, spacing: float = 0) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}".strip()
            if line and SANS_M.width(trial, size, weight, spacing) > max_w:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    return lines


# ---------- svg primitives ----------

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def T(x, y, s, size, weight=400, fill=TEXT, anchor="start", ls=0.0, mono=False, opacity=None) -> str:
    extra = f' opacity="{opacity}"' if opacity is not None else ""
    spacing = f' letter-spacing="{ls}"' if ls else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO if mono else SANS}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{spacing}{extra}>{esc(s)}</text>')


def para(x, y, s, size, weight, max_w, lh=1.35, fill=TEXT, ls=0.0) -> tuple[str, float]:
    """Wrapped text. `y` is the top of the block; returns (svg, height)."""
    lines = wrap(s, size, weight, max_w, ls)
    out = "".join(T(x, y + size * 0.82 + i * size * lh, line, size, weight, fill, ls=ls) for i, line in enumerate(lines))
    return out, len(lines) * size * lh


def rect(x, y, w, h, r=16, fill=SURF, stroke=BORDER, sw=1.5, extra="") -> str:
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}"{s} {extra}/>'


def mascot(x, y, size, look=0.0) -> str:
    """The Stash mascot (same shapes as frontend/public/stash.svg). `look` shifts the pupils, -1..1."""
    k = size / 64
    p = 1.6 * look
    return (f'<g transform="translate({x:.1f},{y:.1f}) scale({k:.4f})">'
            '<rect x="6" y="13" width="52" height="10" rx="4" fill="#C8F031" stroke="#09090B" stroke-width="2.5" '
            'transform="rotate(-5 6 23)"/>'
            '<rect x="9" y="21" width="46" height="36" rx="11" fill="#E4E4E7" stroke="#09090B" stroke-width="2.5"/>'
            '<ellipse cx="24" cy="37" rx="7" ry="7.5" fill="#fff" stroke="#09090B" stroke-width="2.5"/>'
            '<ellipse cx="40" cy="37" rx="7" ry="7.5" fill="#fff" stroke="#09090B" stroke-width="2.5"/>'
            f'<circle cx="{24 + p:.2f}" cy="37" r="3.3" fill="#09090B"/>'
            f'<circle cx="{40 + p:.2f}" cy="37" r="3.3" fill="#09090B"/></g>')


def logo(x, y, size) -> str:
    """Mascot + wordmark; `y` is the top. Size is the mascot's."""
    return mascot(x, y, size) + T(x + size * 1.18, y + size * 0.74, "Stash", size * 0.66, 700, ls=-size * 0.012)


def badge(cx, cy, n, r=21) -> str:
    return (f'<circle cx="{cx}" cy="{cy}" r="{r + 5}" fill="{ACCENT}" opacity="0.18"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ACCENT}" stroke="{BG}" stroke-width="3"/>'
            + T(cx, cy + r * 0.38, str(n), r * 1.05, 700, BG, "middle"))


def pill(x, y, label, size=22, fill=ACCENT, ink=BG, pad=18, dot=False) -> tuple[str, float]:
    w = SANS_M.width(label, size, 650 if fill == ACCENT else 500, size * 0.06) + pad * 2 + (size * 0.9 if dot else 0)
    h = size * 1.9
    inner = (f'<circle cx="{x + pad + size * 0.25:.1f}" cy="{y + h / 2:.1f}" r="{size * 0.22:.1f}" fill="{ACCENT}"/>'
             if dot else "")
    tx = x + pad + (size * 0.9 if dot else 0)
    return (rect(x, y, w, h, h / 2, fill, None if fill == ACCENT else BORDER2) + inner
            + T(tx, y + h / 2 + size * 0.36, label, size, 650 if fill == ACCENT else 500, ink, ls=size * 0.06), w)


# ---------- cards ----------

def card_note(x, y, w, h, color, title, lines, size=22, glow=False) -> str:
    bg, ink = NOTE[color]
    out = rect(x, y, w, h, 18, bg, ACCENT if glow else "#00000000", 3 if glow else 0, 'filter="url(#shadow)"')
    out += T(x + 26, y + 26 + size, title, size * 1.05, 700, ink)
    cy = y + 26 + size * 2.4
    for line in lines:
        wrapped = wrap(line, size, 400, w - 78)
        out += f'<circle cx="{x + 34}" cy="{cy - size * 0.33:.1f}" r="{size * 0.15:.1f}" fill="{ink}"/>'
        for i, part in enumerate(wrapped):
            out += T(x + 52, cy + i * size * 1.35, part, size, 400, ink, opacity=0.92)
        cy += len(wrapped) * size * 1.35 + size * 0.35
    return out


def card_link(x, y, w, site, title, desc, hue=("#C8F031", "#3DD9C1"), size=21, glow=False) -> tuple[str, float]:
    thumb = w * 0.42
    gid = f"g{abs(hash((x, y, site))) % 99999}"
    t_svg, t_h = para(x + 24, y + thumb + 58, title, size * 1.08, 650, w - 48, 1.3)
    d_svg, d_h = para(x + 24, y + thumb + 66 + t_h, desc, size * 0.92, 400, w - 48, 1.4, TEXT2)
    h = thumb + 66 + t_h + d_h + 24
    out = (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{hue[0]}"/>'
           f'<stop offset="1" stop-color="{hue[1]}"/></linearGradient>'
           f'<clipPath id="c{gid}"><rect x="{x}" y="{y}" width="{w}" height="{thumb}" rx="18"/></clipPath></defs>'
           + rect(x, y, w, h, 18, SURF, ACCENT if glow else BORDER, 3 if glow else 1.5, 'filter="url(#shadow)"')
           + f'<g clip-path="url(#c{gid})"><rect x="{x}" y="{y}" width="{w}" height="{thumb}" fill="url(#{gid})" opacity="0.9"/>'
           f'<circle cx="{x + w * 0.78}" cy="{y + thumb * 0.3}" r="{thumb * 0.5}" fill="#09090B" opacity="0.14"/>'
           f'<rect x="{x + 28}" y="{y + thumb * 0.34}" width="{w * 0.42}" height="{thumb * 0.13}" rx="6" fill="#09090B" opacity="0.55"/>'
           f'<rect x="{x + 28}" y="{y + thumb * 0.56}" width="{w * 0.28}" height="{thumb * 0.09}" rx="5" fill="#09090B" opacity="0.3"/>'
           f'</g><line x1="{x}" y1="{y + thumb}" x2="{x + w}" y2="{y + thumb}" stroke="{BORDER}" stroke-width="1.5"/>'
           f'<circle cx="{x + 32}" cy="{y + thumb + 30}" r="8" fill="{hue[0]}"/>'
           + T(x + 48, y + thumb + 36, site, size * 0.8, 500, TEXT3) + t_svg + d_svg)
    return out, h


def card_code(x, y, w, h, filename, lines, size=20) -> str:
    out = rect(x, y, w, h, 18, SURF, BORDER, 1.5, 'filter="url(#shadow)"')
    out += f'<line x1="{x}" y1="{y + 52}" x2="{x + w}" y2="{y + 52}" stroke="{BORDER}" stroke-width="1.5"/>'
    for i, c in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
        out += f'<circle cx="{x + 26 + i * 20}" cy="{y + 26}" r="6" fill="{c}" opacity="0.85"/>'
    out += T(x + 96, y + 33, filename, size * 0.85, 500, TEXT2, mono=True)
    for i, segs in enumerate(lines):
        spans = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in segs)
        out += (f'<text x="{x + 26}" y="{y + 92 + i * size * 1.6:.1f}" font-family="{MONO}" font-size="{size}" '
                f'xml:space="preserve">{spans}</text>')
    return out


def card_image(x, y, w, h, caption, size=20) -> str:
    gid = f"i{abs(hash((x, y))) % 99999}"
    ph = h - 64
    return (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2B3A67"/>'
            f'<stop offset="0.65" stop-color="#E07A5F"/><stop offset="1" stop-color="#F2CC8F"/></linearGradient>'
            f'<clipPath id="c{gid}"><rect x="{x}" y="{y}" width="{w}" height="{ph}" rx="18"/></clipPath></defs>'
            + rect(x, y, w, h, 18, SURF, BORDER, 1.5, 'filter="url(#shadow)"')
            + f'<g clip-path="url(#c{gid})"><rect x="{x}" y="{y}" width="{w}" height="{ph}" fill="url(#{gid})"/>'
            f'<circle cx="{x + w * 0.68}" cy="{y + ph * 0.5}" r="{ph * 0.16}" fill="#FFE8B0"/>'
            f'<path d="M{x} {y + ph} L{x + w * 0.3} {y + ph * 0.55} L{x + w * 0.5} {y + ph * 0.78} L{x + w * 0.72} '
            f'{y + ph * 0.48} L{x + w} {y + ph * 0.86} L{x + w} {y + ph} Z" fill="#1B1B2F" opacity="0.92"/></g>'
            + T(x + 22, y + ph + 40, caption, size, 400, TEXT2))


def card_text(x, y, s, size) -> str:
    return T(x, y + size * 0.85, s, size, 700, TEXT, ls=-size * 0.03)


# ---------- product scenes (each in its own 900-wide box) ----------

def canvas_bg(w, h) -> str:
    return (rect(0, 0, w, h, 30, CANVAS, BORDER, 2) +
            f'<rect x="0" y="0" width="{w}" height="{h}" rx="30" fill="url(#dots)"/>')


@dataclass
class Visual:
    svg: str
    w: float
    h: float


def visual_canvas(anim=None) -> Visual:
    """Concept B: a canvas full of mixed cards."""
    a = anim or (lambda s, *_: s)
    link, lh = card_link(40, 44, 370, "linear.app/pricing", "Linear pricing: plans for every team",
                         "Free, Basic $8 and Business $14 per user, per month.")
    out = canvas_bg(900, 860)
    out += a(link, "pop", 0.0)
    out += a(card_note(450, 44, 410, 262, "yellow", "Launch plan",
                       ["Beta invites go out Monday", "Pricing page by Friday", "Record the demo video"]), "pop", 0.15)
    out += a(card_code(450, 336, 410, 236, "pricing.ts", [
        [("export const ", "#C792EA"), ("plans", TEXT), (" = {", TEXT2)],
        [("  starter: ", TEXT2), ("12", ACCENT), (",", TEXT2)],
        [("  team: ", TEXT2), ("29", ACCENT), (",", TEXT2)],
        [("};", TEXT2)]]), "pop", 0.3)
    out += a(card_image(40, 44 + lh + 34, 370, 860 - 44 - lh - 34 - 44, "Whiteboard from Tuesday"), "pop", 0.45)
    out += a(card_note(450, 602, 410, 214, "green", "Ideas", ["Annual plan, 2 months free", "Student discount"]),
             "pop", 0.6)
    return Visual(out, 900, 860)


ANSWER = [["Two cards mention pricing."], ["Linear Basic is $8 per user", 1], ["and your note says $12 a month", 2]]


def chat_panel(x, y, w, h, anim=None) -> str:
    a = anim or (lambda s, *_: s)
    out = rect(x, y, w, h, 24, SURF, BORDER2, 1.5, 'filter="url(#shadow-lg)"')
    out += mascot(x + 26, y + 22, 44) + T(x + 84, y + 44, "Ask Stash", 22, 650) + \
        T(x + 84, y + 70, "Answers only from your cards", 16, 400, TEXT3)
    out += f'<line x1="{x}" y1="{y + 96}" x2="{x + w}" y2="{y + 96}" stroke="{BORDER}" stroke-width="1.5"/>'
    q = "What did I save about pricing?"
    qw = SANS_M.width(q, 21, 450) + 40
    out += a(rect(x + w - 24 - qw, y + 124, qw, 54, 16, SURF3, None) + T(x + w - 44, y + 158, q, 21, 450, anchor="end"),
             "pop", 0.0)
    out += a(T(x + 24, y + 222, "Searched your cards · Found 2 · Checked the answer", 15, 400, TEXT3), "fade", 0.5)
    ly = y + 266
    for i, line in enumerate(ANSWER):
        cx = x + 24
        segs = ""
        for seg in line:
            if isinstance(seg, int):
                segs += (f'<circle cx="{cx + 13:.1f}" cy="{ly - 7:.1f}" r="13" fill="{ACCENT}"/>'
                         + T(cx + 13, ly - 1, str(seg), 15, 700, BG, "middle"))
                cx += 30
            else:
                segs += T(cx, ly, seg, 21, 400, TEXT)
                cx += SANS_M.width(seg, 21, 400) + 6
        out += a(segs, "fade", 0.9 + i * 0.25)
        ly += 34
    ry = ly + 18
    for i, (n, kind, title) in enumerate([(1, "Link", "Linear pricing: plans for every team"),
                                          (2, "Note", "Pricing ideas")]):
        row = (rect(x + 24, ry, w - 48, 54, 12, SURF, BORDER) + f'<circle cx="{x + 52}" cy="{ry + 27}" r="13" '
               f'fill="{ACCENT}" opacity="0.2"/>' + T(x + 52, ry + 33, str(n), 15, 700, ACCENT, "middle")
               + T(x + 78, ry + 33, kind, 15, 500, TEXT3) + T(x + 126, ry + 33, title, 18, 450))
        out += a(row, "pop", 1.7 + i * 0.15)
        ry += 66
    out += rect(x + 24, y + h - 78, w - 48, 54, 14, SURF2, BORDER) + T(x + 46, y + h - 44, "Ask about this canvas…",
                                                                      18, 400, TEXT3)
    out += f'<rect x="{x + w - 70}" y="{y + h - 72}" width="40" height="40" rx="10" fill="{ACCENT}"/>' + \
        f'<path d="M{x + w - 50} {y + h - 42} v-18 m-7 7 l7 -7 l7 7" stroke="{BG}" stroke-width="3" fill="none" ' \
        'stroke-linecap="round" stroke-linejoin="round"/>'
    return out


def visual_ask(anim=None) -> Visual:
    """Concept A: a question answered from two cards, which light up with their citation numbers."""
    a = anim or (lambda s, *_: s)
    out = canvas_bg(900, 880)
    link, lh = card_link(36, 60, 360, "linear.app/pricing", "Linear pricing: plans for every team",
                         "Free, Basic $8 and Business $14 per user, per month.", glow=True)
    out += a(link, "fade", 0.0)
    out += a(card_note(36, 60 + lh + 44, 360, 250, "yellow", "Pricing ideas",
                       ["Start at $12 a month", "Team plan at $29", "Annual: 2 months free"], glow=True), "fade", 0.0)
    h = 60 + lh + 44 + 250 + 60
    out += a(badge(40, 64, 1), "badge", 2.0) + a(badge(40, 64 + lh + 44, 2), "badge", 2.2)
    out += chat_panel(436, 40, 440, h - 80, anim)
    return Visual(canvas_bg(900, h) + out[len(canvas_bg(900, 880)):], 900, h)


def email_preview(x, y, w) -> str:
    h = 300
    out = rect(x, y, w, h, 20, "#F4F4F5", None, 0, 'filter="url(#shadow-lg)"')
    out += rect(x + 24, y + 70, w - 48, h - 94, 14, "#FFFFFF", "#E4E4E7", 1.2)
    out += mascot(x + 26, y + 18, 34) + T(x + 68, y + 43, "Stash", 19, 700, "#09090B")
    out += T(x + w - 26, y + 43, "Reminder: Renew passport", 15, 500, "#71717A", "end")
    pw = SANS_M.width("REMINDER", 12, 700, 0.8) + 22
    out += rect(x + 50, y + 96, pw, 24, 12, ACCENT, None) + T(x + 61, y + 113, "REMINDER", 12, 700, "#09090B", ls=0.8)
    out += T(x + 50, y + 160, "Renew passport", 28, 700, "#09090B", ls=-0.5)
    out += T(x + 50, y + 194, "Appointment at 10:30 today. Bring two photos.", 17, 400, "#3F3F46")
    out += rect(x + 50, y + 216, 190, 46, 10, "#09090B", None) + T(x + 145, y + 245, "Open the card →", 17, 600,
                                                                  "#FFFFFF", "middle")
    return out


def visual_remind(anim=None) -> Visual:
    """Concept C: a card with a reminder, the phone notification, and the email."""
    a = anim or (lambda s, *_: s)
    out = canvas_bg(900, 880)
    note = card_note(60, 60, 430, 240, "pink", "Renew passport",
                     ["Appointment Thursday, 10:30 AM", "Bring two photos"])
    chip, _ = pill(520, 92, "Reminder · Thu 9:00 AM", 19, SURF2, TEXT)
    out += a(note + f'<path d="M490 135 h30" stroke="{BORDER2}" stroke-width="2" stroke-dasharray="4 5"/>' + chip,
             "fade", 0.0)
    # phone notification
    nx, ny, nw = 120, 360, 720
    notif = (rect(nx, ny, nw, 150, 30, "#1C1C1F", BORDER2, 1.5, 'filter="url(#shadow-lg)"')
             + rect(nx + 26, ny + 32, 60, 60, 15, BG, BORDER2) + mascot(nx + 32, ny + 38, 48)
             + T(nx + 106, ny + 50, "STASH", 16, 650, TEXT2, ls=1.2) + T(nx + nw - 30, ny + 50, "now", 16, 400, TEXT3,
                                                                          "end")
             + T(nx + 106, ny + 84, "Reminder: Renew passport", 24, 650)
             + T(nx + 106, ny + 116, "Appointment at 10:30 today. Open the card →", 19, 400, TEXT2))
    out += a(notif, "drop", 0.5)
    out += a(email_preview(150, 560, 600), "pop", 1.1)
    return Visual(out, 900, 880)


# ---------- ad copy ----------

@dataclass
class Concept:
    key: str
    eyebrow: str
    lines: list[str]  # the last line is highlighted
    sub: str
    visual: callable


CONCEPTS = [
    Concept("ask", "Ask Stash", ["Stop digging.", "Just ask."],
            "Stash answers from your own links, notes and screenshots, and points to the exact card.", visual_ask),
    Concept("canvas", "One canvas", ["Everything you save,", "on one canvas."],
            "Links, notes, code and images side by side. Drag them where they make sense.", visual_canvas),
    Concept("remind", "Reminders", ["Saved it for later?", "Later is now."],
            "Set a reminder on any card. Stash emails you right on time, with the card one tap away.",
            visual_remind),
]


def headline(x, y, lines, size, max_w, center=False) -> tuple[str, float]:
    """Headline with the last line in the accent colour. `y` is the top."""
    out, cy = "", y
    anchor = "middle" if center else "start"
    for i, line in enumerate(lines):
        for part in wrap(line, size, 700, max_w, -size * 0.035):
            cy += size * 1.04
            out += T(x, cy - size * 0.2, part, size, 700, ACCENT if i == len(lines) - 1 else TEXT, anchor,
                     ls=-size * 0.035)
    return out, cy - y + size * 0.15


def cta(x, y, size=28, center=False) -> tuple[str, float, float]:
    label = "Try Stash free  →"
    w = SANS_M.width(label, size, 650) + size * 2.2
    h = size * 2.3
    if center:
        x -= w / 2
    out = (rect(x, y, w, h, h / 2, ACCENT, None) + T(x + w / 2, y + h / 2 + size * 0.36, label, size, 650, BG, "middle"))
    return out, w, h


# ---------- documents ----------

def font_css() -> str:
    sans = base64.b64encode(SANS_FILE.read_bytes()).decode()
    mono = base64.b64encode(MONO_FILE.read_bytes()).decode()
    return ("@font-face{font-family:'Geist';font-weight:100 900;font-style:normal;"
            f"src:url(data:font/woff2;base64,{sans}) format('woff2');}}"
            "@font-face{font-family:'Geist Mono';font-weight:100 900;font-style:normal;"
            f"src:url(data:font/woff2;base64,{mono}) format('woff2');}}")


FONT_CSS = font_css()


def svg_doc(w, h, body, extra_css="", title="Stash") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<title>{esc(title)}</title>
<defs>
<style>{FONT_CSS}{extra_css}</style>
<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.6" fill="#26262B"/></pattern>
<pattern id="bgdots" width="34" height="34" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.4" fill="#1A1A1E"/></pattern>
<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.22"/>
<stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></radialGradient>
<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#000" flood-opacity="0.45"/></filter>
<filter id="shadow-lg" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="24" stdDeviation="30" flood-color="#000" flood-opacity="0.6"/></filter>
</defs>
<rect width="{w}" height="{h}" fill="{BG}"/>
<rect width="{w}" height="{h}" fill="url(#bgdots)"/>
{body}
</svg>"""


def place(v: Visual, x, y, scale) -> str:
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({scale:.4f})">{v.svg}</g>'


def glow(cx, cy, r) -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#glow)"/>'


def reel(c: Concept) -> str:
    """1080x1920, 9:16. Words stay out of the top 220 px and the bottom ~400 px, where Instagram draws its UI."""
    W, H = 1080, 1920
    out = glow(980, 260, 620) + glow(120, 1700, 560)
    out += logo(90, 214, 64)
    ey, _ = pill(90, 330, c.eyebrow.upper(), 22, SURF2, TEXT, dot=True)
    out += ey
    hl, hh = headline(90, 400, c.lines, 92, 900)
    out += hl
    sub, sh = para(90, 400 + hh + 18, c.sub, 36, 400, 880, 1.38, TEXT2)
    out += sub
    btn, _, bh = cta(90, 400 + hh + sh + 56, 30)
    out += btn + T(90 + 380, 400 + hh + sh + 56 + bh / 2 + 11, URL, 28, 500, TEXT2)
    vy = 400 + hh + sh + 56 + bh + 70
    v = c.visual()
    scale = min(900 / v.w, (H - 40 - vy) / v.h)
    out += place(v, (W - v.w * scale) / 2, vy, scale)
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · Reel")


def horizontal(c: Concept, W=1920, H=1080) -> str:
    """16:9 for YouTube, Facebook and in-stream placements."""
    out = glow(1500, 200, 760) + glow(200, 1000, 520)
    out += logo(120, 120, 64)
    ey, _ = pill(120, 250, c.eyebrow.upper(), 22, SURF2, TEXT, dot=True)
    out += ey
    hl, hh = headline(120, 318, c.lines, 76, 820)
    out += hl
    sub, sh = para(120, 318 + hh + 20, c.sub, 32, 400, 720, 1.4, TEXT2)
    out += sub
    btn, _, bh = cta(120, 318 + hh + sh + 60, 28)
    out += btn + T(120, 318 + hh + sh + 60 + bh + 54, URL, 26, 500, TEXT3)
    v = c.visual()
    scale = min(840 / v.w, (H - 160) / v.h)
    out += place(v, W - 120 - v.w * scale, (H - v.h * scale) / 2, scale)
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · 16:9")


def link_banner(c: Concept, W=1200, H=628) -> str:
    """1200x628 link ads and 1200x630 link previews (Open Graph)."""
    out = glow(980, 120, 520)
    out += logo(64, 60, 44)
    hl, hh = headline(64, 150, c.lines, 54, 560)
    out += hl
    sub, _ = para(64, 150 + hh + 14, c.sub, 22, 400, 520, 1.4, TEXT2)
    out += sub
    btn, _, bh = cta(64, H - 64 - 46, 20)
    out += btn + T(64 + 230, H - 64 - 46 + bh / 2 + 7, URL, 20, 500, TEXT2)
    v = c.visual()
    scale = min(520 / v.w, (H - 64) / v.h)
    out += place(v, W - 40 - v.w * scale, (H - v.h * scale) / 2, scale)
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · Link banner")


def square(c: Concept) -> str:
    """1080x1350 (4:5), the feed size Instagram shows largest."""
    W, H = 1080, 1350
    out = glow(980, 200, 560)
    out += logo(80, 80, 52)
    hl, hh = headline(80, 168, c.lines, 70, 920)
    out += hl
    sub, sh = para(80, 168 + hh + 12, c.sub, 30, 400, 900, 1.38, TEXT2)
    out += sub
    vy = 168 + hh + sh + 48
    v = c.visual()
    scale = min(920 / v.w, (H - 170 - vy) / v.h)
    out += place(v, (W - v.w * scale) / 2, vy, scale)
    btn, bw, bh = cta(80, H - 80 - 64, 26)
    out += btn + T(80 + bw + 24, H - 80 - 64 + bh / 2 + 9, URL, 26, 500, TEXT2)
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · Feed 4:5")


# ---------- stories and LinkedIn ----------

LAUNCH = Concept("launch", "Now live", ["Introducing", "Stash."],
                 "A canvas for everything you save. It answers your questions and reminds you on time.", visual_canvas)
FEATURES = ["One canvas", "Ask your cards", "Email reminders"]


def para_center(cx, y, s, size, weight, max_w, lh=1.35, fill=TEXT2) -> tuple[str, float]:
    lines = wrap(s, size, weight, max_w)
    out = "".join(T(cx, y + size * 0.82 + i * size * lh, line, size, weight, fill, "middle")
                  for i, line in enumerate(lines))
    return out, len(lines) * size * lh


def logo_width(size) -> float:
    return size * 1.18 + SANS_M.width("Stash", size * 0.66, 700, -size * 0.012)


def chip_row(cx, y, labels, size=24, gap=14, center=True) -> tuple[str, float]:
    widths = [pill(0, 0, label, size, SURF2, TEXT, dot=True)[1] for label in labels]
    total = sum(widths) + gap * (len(labels) - 1)
    x = cx - total / 2 if center else cx
    out = ""
    for label, w in zip(labels, widths, strict=True):
        out += pill(x, y, label, size, SURF2, TEXT, dot=True)[0]
        x += w + gap
    return out, size * 1.9


def story(c: Concept) -> str:
    """1080x1920 Instagram/Facebook Story. Instagram covers the top ~250 px (progress bar, profile) and the bottom
    ~340 px (reply bar); the gap just above that is left empty for the link sticker."""
    W, H = 1080, 1920
    out = glow(W / 2, 300, 700) + glow(W / 2, 1500, 520)
    out += logo((W - logo_width(60)) / 2, 262, 60)
    ew = pill(0, 0, c.eyebrow.upper(), 22, SURF2, TEXT, dot=True)[1]
    out += pill((W - ew) / 2, 372, c.eyebrow.upper(), 22, SURF2, TEXT, dot=True)[0]
    hl, hh = headline(W / 2, 440, c.lines, 96, 960, center=True)
    out += hl
    sub, sh = para_center(W / 2, 440 + hh + 18, c.sub, 34, 400, 860)
    out += sub
    y = 440 + hh + sh + 48
    if c is LAUNCH:
        chips, ch = chip_row(W / 2, y, FEATURES)
        out += chips
        y += ch + 40
    v = c.visual()
    scale = min(940 / v.w, (1455 - y) / v.h)
    out += place(v, (W - v.w * scale) / 2, y, scale)
    out += T(W / 2, 1524, "Tap the link to try it free", 32, 600, TEXT, "middle")
    out += (f'<path d="M{W / 2 - 16} 1550 l16 16 l16 -16" stroke="{ACCENT}" stroke-width="5" fill="none" '
            'stroke-linecap="round" stroke-linejoin="round"/>')
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · Story")


def linkedin_post(c: Concept) -> str:
    """1200x1200, the image size LinkedIn shows largest in the feed on both desktop and mobile."""
    W, H = 1200, 1200
    out = glow(1050, 120, 620)
    out += logo(72, 64, 50)
    out += pill(72, 160, c.eyebrow.upper(), 21, SURF2, TEXT, dot=True)[0]
    if c is LAUNCH:  # one line, the name in the accent colour
        lead = "Introducing "
        hl = (T(72, 226 + 70 * 0.84, lead, 70, 700, ls=-70 * 0.035)
              + T(72 + SANS_M.width(lead, 70, 700, -70 * 0.035), 226 + 70 * 0.84, "Stash.", 70, 700, ACCENT,
                  ls=-70 * 0.035))
        hh = 70 * 1.19
    else:
        hl, hh = headline(72, 226, c.lines, 66, 1060)
    out += hl
    sub, sh = para(72, 226 + hh + 14, c.sub, 28, 400, 1000, 1.4, TEXT2)
    out += sub
    y = 226 + hh + sh + 40
    if c is LAUNCH:
        chips, ch = chip_row(72, y, FEATURES, 22, center=False)
        out += chips
        y += ch + 36
    footer = H - 112
    v = c.visual()
    scale = min(1056 / v.w, (footer - 36 - y) / v.h)
    out += place(v, (W - v.w * scale) / 2, y, scale)
    out += f'<line x1="72" y1="{footer}" x2="{W - 72}" y2="{footer}" stroke="{BORDER}" stroke-width="1.5"/>'
    out += T(72, footer + 58, URL, 26, 600, TEXT)
    out += T(W - 72, footer + 58, "Free · Sign in with Google, X or email", 24, 400, TEXT3, "end")
    return svg_doc(W, H, out, title=f"Stash · {c.eyebrow} · LinkedIn")


def linkedin_cover() -> str:
    """1584x396 profile cover. LinkedIn puts the profile photo over the bottom left, so that corner stays empty."""
    W, H = 1584, 396
    out = glow(1200, 60, 520) + glow(420, 400, 380)
    v = visual_canvas()
    scale = (H - 64) / v.h
    out += place(v, 400, 32, scale)
    x = 820
    out += logo(x, 64, 46)
    hl, hh = headline(x, 140, ["Everything you save,", "on one canvas."], 52, 700)
    out += hl
    out += T(x, 140 + hh + 40, "Save it. Ask it. Get reminded.", 24, 500, TEXT2)
    out += T(x, 140 + hh + 76, URL, 22, 600, ACCENT)
    return svg_doc(W, H, out, title="Stash · LinkedIn cover")


# ---------- animated reel (HTML + CSS, captured frame by frame) ----------

# Cuts sit on the soundtrack's bar lines (120 BPM, 2 s bars) so every scene change lands on the beat.
DURATION = 18.0
SCENES = [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 15.0), (15.0, DURATION)]
EVENTS: list[tuple[float, str]] = []  # (time, animation kind), for the sound effects
FADE = 0.4

ANIM_CSS = """
g.a{transform-box:fill-box;transform-origin:center;animation-duration:.7s;animation-fill-mode:both;
    animation-timing-function:cubic-bezier(.16,1,.3,1)}
g.pop{animation-name:pop} g.fade{animation-name:fade} g.badge{animation-name:badge}
g.drop{animation-name:drop} g.rise{animation-name:rise;animation-duration:.9s}
@keyframes pop{0%{opacity:0;transform:translateY(28px) scale(.96)}100%{opacity:1;transform:none}}
@keyframes rise{0%{opacity:0;transform:translateY(40px)}100%{opacity:1;transform:none}}
@keyframes fade{0%{opacity:0}100%{opacity:1}}
@keyframes drop{0%{opacity:0;transform:translateY(-90px)}100%{opacity:1;transform:none}}
@keyframes badge{0%{opacity:0;transform:scale(.2)}70%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:none}}
g.zoom{transform-box:fill-box;transform-origin:center;animation:zoom 17s linear both}
"""


def fade_css(name, start, end, duration, fade=FADE) -> str:
    """Opacity keyframes that show `g.<name>` from `start` to `end` on a timeline `duration` seconds long."""
    p = lambda t: f"{max(0.0, min(100.0, t / duration * 100)):.3f}%"
    first, last = start <= 0, end >= duration
    frames = [f"0%{{opacity:{1 if first else 0}}}"]
    if not first:
        frames += [f"{p(start)}{{opacity:0}}", f"{p(start + fade)}{{opacity:1}}"]
    if not last:
        frames += [f"{p(end - fade)}{{opacity:1}}", f"{p(end)}{{opacity:0}}"]
    frames.append(f"100%{{opacity:{1 if last else 0}}}")
    return (f"@keyframes {name}{{{' '.join(frames)}}}"
            f"g.{name}{{animation:{name} {duration}s linear both}}")


def animator(t0):
    def a(content, kind, t):
        EVENTS.append((t0 + t, kind))
        return f'<g class="a {kind}" style="animation-delay:{t0 + t:.2f}s">{content}</g>'
    return a


def drift(content, start, end) -> str:
    """A slow push-in across the whole scene, so long explainer scenes never sit still."""
    return (f'<g class="drift" style="animation-delay:{start:.2f}s;animation-duration:{end - start:.2f}s">'
            f'{content}</g>')


def scene_hook(a, W, H, vertical) -> str:
    hook = ""
    scatter = [(-6, "link"), (5, "note"), (-3, "code"), (7, "image"), (-8, "note2")]
    cx0, cy0 = (W / 2, H * 0.68) if vertical else (W * 0.66, H / 2)
    spots = ([(-380, -260), (60, -330), (-300, 120), (120, 60), (-90, -40)] if vertical else
             [(-420, -330), (40, -360), (-380, 60), (100, 20), (-160, -150)])
    for k, ((rot, kind), (dx, dy)) in enumerate(zip(scatter, spots, strict=True)):
        x, y = cx0 + dx, cy0 + dy
        if kind == "link":
            piece, _ = card_link(x, y, 320, "youtube.com", "How to price a SaaS product", "Saved 3 weeks ago")
        elif kind == "note":
            piece = card_note(x, y, 300, 190, "yellow", "Gift ideas", ["Noise-cancelling headphones", "Cookbook"])
        elif kind == "code":
            piece = card_code(x, y, 330, 170, "fetch.js", [[("await ", "#C792EA"), ("fetch(url)", TEXT)],
                                                          [("  .then(r => r.json())", TEXT2)]])
        elif kind == "image":
            piece = card_image(x, y, 300, 230, "screenshot_2041.png")
        else:
            piece = card_note(x, y, 300, 170, "blue", "Book list", ["Atomic Habits", "Deep Work"])
        hook += f'<g transform="rotate({rot} {x + 150} {y + 100})">{a(piece, "drop", 0.15 + k * 0.18)}</g>'
    if vertical:
        hl1, _ = headline(W / 2, 330, ["You saved it somewhere.", "Now where is it?"], 84, 940, center=True)
    else:
        hl1, _ = headline(140, 380, ["You saved it", "somewhere.", "Now where is it?"], 92, 760)
    return logo(90 if vertical else 120, 200 if vertical else 110, 56) + a(hl1, "rise", 0.0) + hook


def scene_product(a, W, H, vertical, concept, span=None) -> str:
    """`span` (start, end) marks the explainer version: the voice and captions replace the supporting line."""
    v = concept.visual(anim=a)
    if vertical:
        ey, _ = pill(90, 330, concept.eyebrow.upper(), 22, SURF2, TEXT, dot=True)
        hl, hh = headline(90, 400, concept.lines, 88, 900)
        sub, sh = para(90, 400 + hh + 16, concept.sub, 34, 400, 880, 1.38, TEXT2)
        if span:
            sub, sh = "", CAPTION_BAND - 54
        vy = 400 + hh + sh + 70
        scale = min(900 / v.w, (H - 60 - vy) / v.h)
        visual = place(v, (W - v.w * scale) / 2, vy, scale)
    else:
        ey, _ = pill(120, 250, concept.eyebrow.upper(), 22, SURF2, TEXT, dot=True)
        hl, hh = headline(120, 318, concept.lines, 76, 820)
        sub, sh = para(120, 318 + hh + 20, concept.sub, 30, 400, 700, 1.4, TEXT2)
        if span:
            sub = ""
        scale = min(840 / v.w, (H - 140) / v.h)
        visual = place(v, W - 120 - v.w * scale, (H - v.h * scale) / 2, scale)
    if span:
        visual = drift(visual, *span)
    return (logo(90 if vertical else 120, 200 if vertical else 110, 56)
            + a(ey, "fade", 0) + a(hl, "rise", 0.05) + a(sub, "rise", 0.2) + visual)


def scene_intro(a, W, H, vertical) -> str:
    """Explainer only: the name, after the hook."""
    cx = W / 2
    top = H * 0.27 if vertical else H * 0.16
    out = a(mascot(cx - 150, top, 300, look=-0.4), "badge", 0.0)
    out += a(T(cx, top + 470, "Meet Stash.", 150 if vertical else 160, 700, anchor="middle", ls=-5), "rise", 0.25)
    out += a(T(cx, top + 560, "One place for everything you save.", 46, 500, TEXT2, "middle"), "rise", 0.45)
    return out


def scene_end(a, W, H, vertical) -> str:
    cx = W / 2
    top = H * 0.30 if vertical else H * 0.2
    end = a(mascot(cx - 120, top, 240, look=0.4), "badge", 0.0)
    end += a(T(cx, top + 380, "Stash", 140, 700, anchor="middle", ls=-5), "rise", 0.15)
    end += a(T(cx, top + 460, "Everything you save, on one canvas.", 40 if vertical else 44, 500, TEXT2, "middle"),
             "rise", 0.3)
    btn, _, _ = cta(cx, top + 540, 34, center=True)
    end += a(btn, "pop", 0.5) + a(T(cx, top + 700, f"Free · {URL}", 32, 500, TEXT3, "middle"), "fade", 0.7)
    return end


CAPTION_BAND = 170  # vertical explainer: room between headline and visual for two caption lines


def caption_spot(kind, vertical, W, H) -> tuple[float, float | None, str]:
    """(x, top, align) for a scene's captions: under the headline where there is one, else along the bottom."""
    if kind in ("intro", "end"):
        return W / 2, None, "middle"
    if kind == "hook":
        lines = ["You saved it somewhere.", "Now where is it?"] if vertical else ["You saved it", "somewhere.",
                                                                              "Now where is it?"]
        hh = headline(0, 0, lines, 84 if vertical else 92, 940 if vertical else 760)[1]
        return (W / 2, 330 + hh + 40, "middle") if vertical else (140, 380 + hh + 44, "start")
    lines = {c.key: c.lines for c in CONCEPTS}[kind]
    if vertical:
        return W / 2, 400 + headline(0, 0, lines, 88, 900)[1] + 24, "middle"
    return 120, 318 + headline(0, 0, lines, 76, 820)[1] + 30, "start"


def caption_box(text, W, H, vertical, spot) -> str:
    x0, top, align = spot
    size = 40 if vertical else 36
    max_w = 860 if vertical else (800 if align == "start" else 1300)
    lines = wrap(text, size, 600, max_w)
    lh = size * 1.3
    box_w = max(SANS_M.width(line, size, 600) for line in lines) + 56
    box_h = len(lines) * lh + 36
    if top is None:
        top = (1490 if vertical else H - 56) - box_h  # above Instagram's caption and buttons
    bx = x0 - box_w / 2 if align == "middle" else x0 - 28
    out = rect(bx, top, box_w, box_h, 20, "#000000", BORDER2, 1.5, 'fill-opacity="0.72"')
    out += f'<rect x="{bx}" y="{top + 14}" width="4" height="{box_h - 28}" rx="2" fill="{ACCENT}"/>' \
        if align == "start" else ""
    for i, line in enumerate(lines):
        out += T(x0 if align == "middle" else bx + 28, top + 18 + size * 0.95 + i * lh, line, size, 600, "#FFFFFF",
                 align)
    return out


AD_TIMELINE = [("hook", *SCENES[0]), ("canvas", *SCENES[1]), ("ask", *SCENES[2]), ("remind", *SCENES[3]),
               ("end", *SCENES[4])]


def video_svg(vertical: bool, timeline=None, duration: float = DURATION, captions=(), title="Stash · Reel") -> str:
    """`timeline`: (scene, start, end) rows. `captions`: (start, end, text) rows. Explainers pass both; drift is on
    whenever captions are, so the short ad renders exactly as before."""
    timeline = timeline or AD_TIMELINE
    W, H = (1080, 1920) if vertical else (1920, 1080)
    EVENTS.clear()
    css = ANIM_CSS + "".join(fade_css(f"s{i}", s, e, duration) for i, (_, s, e) in enumerate(timeline))
    if captions:
        css += ("g.drift{transform-box:fill-box;transform-origin:center;animation-name:drift;"
                "animation-timing-function:linear;animation-fill-mode:both}"
                "@keyframes drift{from{transform:scale(1)}to{transform:scale(1.045)}}")
        css += "".join(fade_css(f"c{i}", s, e, duration, 0.12) for i, (s, e, _) in enumerate(captions))
    out = glow(W * 0.85, H * 0.15, 700) + glow(W * 0.1, H * 0.9, 600)
    concepts = {c.key: c for c in CONCEPTS}
    for i, (kind, start, end) in enumerate(timeline):
        a = animator(start)
        if kind == "hook":
            body = scene_hook(a, W, H, vertical)
        elif kind == "intro":
            body = scene_intro(a, W, H, vertical)
        elif kind == "end":
            body = scene_end(a, W, H, vertical)
        else:
            body = scene_product(a, W, H, vertical, concepts[kind], (start, end) if captions else None)
        out += f'<g class="s{i}">{body}</g>'
    for i, (start, _, text) in enumerate(captions):
        kind = next(k for k, s, e in timeline if s <= start < e)
        out += f'<g class="c{i}">{caption_box(text, W, H, vertical, caption_spot(kind, vertical, W, H))}</g>'
    return svg_doc(W, H, out, css, title)


# ---------- export ----------

def export_png(page, svg_path: Path, png_path: Path, w: int, h: int) -> None:
    page.set_viewport_size({"width": w, "height": h})
    page.goto(svg_path.as_uri())
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(150)
    page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": w, "height": h})


LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=11"  # what Instagram, TikTok and YouTube normalise to


def render_video(page, svg_text: str, w: int, h: int, mp4: Path, audio: Path, duration: float, fps: int = 30) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        doc = tmpd / "reel.html"
        doc.write_text(f"<!doctype html><html><body style='margin:0;background:{BG}'>{svg_text}</body></html>")
        page.set_viewport_size({"width": w, "height": h})
        page.goto(doc.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        frames = round(duration * fps)
        for f in range(frames):
            page.evaluate("t => document.getAnimations().forEach(a => { a.pause(); a.currentTime = t; })",
                          f * 1000 / fps)
            page.screenshot(path=str(tmpd / f"f{f:04d}.jpg"), type="jpeg", quality=92,
                            clip={"x": 0, "y": 0, "width": w, "height": h})
            if f % 60 == 0:
                print(f"  {mp4.name}: frame {f}/{frames}", flush=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmpd / "f%04d.jpg"),
                        "-i", str(audio), "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-af", LOUDNESS, "-shortest",
                        "-movflags", "+faststart", str(mp4)], check=True)


def m4a(wav: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", LOUDNESS, "-ar", "48000",
                    "-c:a", "aac", "-b:a", "192k", str(wav.with_suffix(".m4a"))], check=True)
    wav.unlink()


def build_ads_video(page) -> None:
    import soundtrack

    secs = f"{DURATION:g}s"
    wav = OUT / "audio" / f"stash-theme-{secs}.wav"
    for vertical, name, w, h in ((True, f"reel-stash-{secs}", 1080, 1920),
                                 (False, f"landscape-stash-{secs}", 1920, 1080)):
        svg = video_svg(vertical)
        soundtrack.render(DURATION, [s for s, _ in SCENES], EVENTS, wav)
        (OUT / "svg" / f"{name}-animated.svg").write_text(svg)
        render_video(page, svg, w, h, OUT / "video" / f"{name}.mp4", wav, DURATION)
        print("wrote", name)
    m4a(wav)


def build_explainer(page) -> None:
    """The narrated version: female voiceover, captions, and the same music ducked under the voice."""
    import soundtrack
    import voiceover

    ex = voiceover.build()
    secs = f"{math.ceil(ex.duration):d}s"
    print(f"explainer: voice {ex.voice}, {ex.duration:g}s, scenes at", [s for _, s, _ in ex.timeline])
    voice_wav = OUT / "audio" / f"explainer-voiceover-{secs}.wav"
    music_wav = OUT / "audio" / "explainer-music.wav"
    mixed_wav = OUT / "audio" / "explainer-mix.wav"
    voiceover.write(ex.track, voice_wav)
    for vertical, name, w, h in ((True, f"explainer-reel-{secs}", 1080, 1920),
                                 (False, f"explainer-landscape-{secs}", 1920, 1080)):
        svg = video_svg(vertical, ex.timeline, ex.duration, ex.captions, "Stash · Explainer")
        soundtrack.render(ex.duration, [s for _, s, _ in ex.timeline], EVENTS, music_wav)
        voiceover.mix(music_wav, voice_wav, mixed_wav)
        (OUT / "svg" / f"{name}-animated.svg").write_text(svg)
        render_video(page, svg, w, h, OUT / "video" / f"{name}.mp4", mixed_wav, ex.duration)
        print("wrote", name)
    m4a(voice_wav)
    music_wav.unlink()
    mixed_wav.unlink()
    lines = [f"{s:.2f} --> {e:.2f}  {text}" for s, e, text in ex.captions]
    (OUT / "video" / f"explainer-captions-{secs}.txt").write_text("\n".join(lines) + "\n")


def main() -> None:
    """Flags: --no-video (images only), --explainer (only the narrated explainer videos)."""
    from playwright.sync_api import sync_playwright

    only_static = "--no-video" in sys.argv
    only_explainer = "--explainer" in sys.argv
    for d in ("svg", "png", "video", "audio"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, str, int, int]] = []
    for c in CONCEPTS:
        jobs += [(f"reel-{c.key}", reel(c), 1080, 1920), (f"landscape-{c.key}", horizontal(c), 1920, 1080),
                 (f"feed-{c.key}", square(c), 1080, 1350), (f"link-{c.key}", link_banner(c), 1200, 628)]
    for c in [*CONCEPTS, LAUNCH]:
        jobs += [(f"story-{c.key}", story(c), 1080, 1920), (f"linkedin-{c.key}", linkedin_post(c), 1200, 1200)]
    jobs.append(("linkedin-cover", linkedin_cover(), 1584, 396))
    og = link_banner(CONCEPTS[1], 1200, 630)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=1)
        if not only_explainer:
            for name, svg, w, h in jobs:
                svg_path = OUT / "svg" / f"{name}.svg"
                svg_path.write_text(svg)
                export_png(page, svg_path, OUT / "png" / f"{name}.png", w, h)
                print("wrote", name)
            og_svg = REPO / "frontend/public/og.svg"
            og_svg.write_text(og)
            export_png(page, og_svg, REPO / "frontend/public/og.png", 1200, 630)
            print("wrote og banner")
        if not only_static:
            if not shutil.which("ffmpeg"):
                sys.exit("ffmpeg is needed for the videos (brew install ffmpeg), or pass --no-video")
            if not only_explainer:
                build_ads_video(page)
            build_explainer(page)
        browser.close()


if __name__ == "__main__":
    main()
