"""Starter canvases. Text here is ours; the cards still go through the normal safety and indexing pipeline."""

from typing import Any

Card = dict[str, Any]


def _note(x: float, y: float, markdown: str, color: str = "yellow", w: float | None = None) -> Card:
    return {"kind": "note", "x": x, "y": y, "w": w, "content": {"markdown": markdown, "color": color}}


def _text(x: float, y: float, text: str, size: str = "xl") -> Card:
    return {"kind": "text", "x": x, "y": y, "content": {"text": text, "size": size}}


TEMPLATES: dict[str, dict[str, Any]] = {
    "reading-list": {
        "title": "Reading list",
        "description": "Articles to read, notes while reading, and what to remember.",
        "cards": [
            _text(0, -120, "Reading list"),
            _note(0, 0, "**To read**\n\nPaste links here. One card per article.", "blue"),
            _note(300, 0, "**Reading now**\n\nDrag the link here when you start.", "yellow"),
            _note(600, 0, "**Done**\n\nMove finished articles here and add a one-line takeaway.", "green"),
            _note(0, 260, "**Takeaways**\n\n- \n- \n- ", "plain", 560),
        ],
    },
    "trip": {
        "title": "Trip planner",
        "description": "Dates, places, bookings and a packing list in one view.",
        "cards": [
            _text(0, -120, "Trip planner"),
            _note(0, 0, "**When**\n\nFrom:\nTo:\n\n**Who's going**\n\n- ", "blue"),
            _note(300, 0, "**Places to see**\n\nPaste map links and blog posts next to this card.", "green"),
            _note(600, 0, "**Bookings**\n\n- Flights:\n- Stay:\n- Transport:", "yellow"),
            _note(0, 260, "**Packing list**\n\n- Passport / ID\n- Chargers\n- Medicines\n- ", "pink"),
            _note(300, 260, "**Budget**\n\n- Travel:\n- Stay:\n- Food:\n- Total:", "plain"),
        ],
    },
    "course": {
        "title": "Course notes",
        "description": "Lectures, readings and exam prep for one course.",
        "cards": [
            _text(0, -120, "Course notes"),
            _note(0, 0, "**Course**\n\nName:\nTeacher:\nExam date:", "blue"),
            _note(300, 0, "**Lecture 1**\n\nKey ideas:\n- \n\nQuestions:\n- ", "yellow"),
            _note(600, 0, "**Readings**\n\nPaste papers and chapters next to this card.", "green"),
            _note(0, 260, "**Exam prep**\n\n- Topics to revise\n- Past papers\n- Formulas", "pink"),
            _note(300, 260, "**Tip**\n\nAsk Stash: *\"What are the key ideas from all lectures?\"*", "plain"),
        ],
    },
    "launch": {
        "title": "Project launch",
        "description": "Goals, timeline, tasks and risks for shipping something.",
        "cards": [
            _text(0, -120, "Project launch"),
            _note(0, 0, "**Goal**\n\nWhat does success look like?\n\n**Launch date**\n\n", "green"),
            _note(300, 0, "**Timeline**\n\n- Week 1:\n- Week 2:\n- Launch:", "blue"),
            _note(600, 0, "**Tasks**\n\n- \n- \n- ", "yellow"),
            _note(0, 260, "**Risks**\n\n- \n\n**Open questions**\n\n- ", "pink"),
            _note(300, 260, "**Research**\n\nPaste competitor links, docs and specs around here.", "plain"),
        ],
    },
    "research": {
        "title": "Research board",
        "description": "Sources, quotes and findings, with a question to answer.",
        "cards": [
            _text(0, -120, "Research board"),
            _note(0, 0, "**Research question**\n\nWhat are you trying to find out?", "blue"),
            _note(300, 0, "**Sources**\n\nPaste links, papers and screenshots around this card.", "yellow"),
            _note(600, 0, "**Quotes**\n\n> ", "plain"),
            _note(0, 260, "**Findings**\n\n- \n- ", "green"),
            _note(300, 260, "**Tip**\n\nAsk Stash to compare what your sources say. Every answer cites its cards.",
                  "pink"),
        ],
    },
    "meeting": {
        "title": "Meeting notes",
        "description": "Agenda, notes, decisions and follow-ups.",
        "cards": [
            _text(0, -120, "Meeting notes"),
            _note(0, 0, "**Agenda**\n\n1. \n2. \n3. ", "blue"),
            _note(300, 0, "**Notes**\n\n", "yellow"),
            _note(600, 0, "**Decisions**\n\n- ", "green"),
            _note(0, 260, "**Follow-ups**\n\n- [who] [what] [when]\n\nSet a reminder on this card so nothing slips.",
                  "pink"),
        ],
    },
}


def listing() -> list[dict[str, Any]]:
    return [{"key": key, "title": t["title"], "description": t["description"], "cards": len(t["cards"])}
            for key, t in TEMPLATES.items()]
