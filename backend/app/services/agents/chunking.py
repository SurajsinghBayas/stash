"""Split text into retrieval chunks: by Markdown heading first, then by paragraph, then by sentence.

Every chunk keeps its section heading, and consecutive chunks overlap a little so a sentence on a boundary is
still found.
"""

import re

TARGET = 1100
OVERLAP = 160
MAX_CHUNKS = 40

HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def clip(text: str, limit: int) -> str:
    """Cut at a word boundary."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return cut[:space] if space > limit // 2 else cut


def _sections(markdown: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in markdown.splitlines():
        m = HEADING.match(line)
        if m:
            sections.append((clip(m.group(2).strip(), 120), []))
        else:
            sections[-1][1].append(line)
    out = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if body:
            out.append((heading, body))
    return out


def _pieces(body: str) -> list[str]:
    """Paragraphs, with any paragraph longer than TARGET broken into sentences (or hard-cut)."""
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para:
            continue
        if len(para) <= TARGET:
            pieces.append(para)
            continue
        for sentence in SENTENCE.split(para):
            while len(sentence) > TARGET:
                head = clip(sentence, TARGET)
                pieces.append(head)
                sentence = sentence[len(head):].lstrip()
            if sentence.strip():
                pieces.append(sentence.strip())
    return pieces


def split(markdown: str) -> list[tuple[str | None, str]]:
    chunks: list[tuple[str | None, str]] = []
    for heading, body in _sections(markdown):
        current = ""
        for piece in _pieces(body):
            if current and len(current) + len(piece) + 2 > TARGET:
                chunks.append((heading, current))
                tail = current[-OVERLAP:]
                current = tail[tail.find(" ") + 1:] if " " in tail else ""
            current = f"{current}\n\n{piece}".strip() if current else piece
        if current:
            chunks.append((heading, current))
        if len(chunks) >= MAX_CHUNKS:
            break
    return chunks[:MAX_CHUNKS]
