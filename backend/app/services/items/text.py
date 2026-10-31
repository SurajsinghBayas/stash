"""What each card contributes to search, digests and AI, and URL normalisation for duplicate detection."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|ref_src$|igshid$|si$)")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)))
    path = parts.path.rstrip("/") or ""
    return urlunsplit(("", host + port, path, query, ""))[2:]


def _strip_markdown(md: str) -> str:
    text = re.sub(r"```.*?```", " ", md, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}(#{1,6}|[-*+]|\d+\.|>)\s*(\[[ xX]\]\s*)?", "", text, flags=re.M)
    text = re.sub(r"[*_`~]", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def search_text(kind: str, content: dict) -> str:
    if kind == "link":
        fields = [content.get("title"), content.get("description"), content.get("site_name"), content.get("url"),
                  content.get("comment")]
    elif kind == "note":
        fields = [_strip_markdown(content.get("markdown", ""))]
    elif kind == "text":
        fields = [content.get("text")]
    elif kind == "code":
        fields = [content.get("filename"), content.get("language"), content.get("source")]
    elif kind == "image":
        fields = [content.get("caption"), content.get("filename")]
    else:
        fields = []
    return "\n".join(f.strip() for f in fields if isinstance(f, str) and f.strip())[:20000]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def title_of(kind: str, content: dict) -> str:
    """Short human label for emails, chat citations and digests."""
    if kind == "link":
        return content.get("title") or content.get("url", "Link")
    if kind == "note":
        first = next((line for line in _strip_markdown(content.get("markdown", "")).splitlines() if line.strip()), "")
        return first[:80] or "Note"
    if kind == "text":
        return (content.get("text") or "Text").strip()[:80]
    if kind == "code":
        return content.get("filename") or f"{content.get('language', 'code')} snippet"
    if kind == "image":
        return content.get("caption") or content.get("filename") or "Image"
    return "Card"


def snippet_of(kind: str, content: dict, limit: int = 160) -> str:
    if kind == "link":
        text = content.get("description") or content.get("url", "")
    elif kind == "note":
        lines = [ln for ln in _strip_markdown(content.get("markdown", "")).splitlines() if ln.strip()]
        text = " ".join(lines[1:])
    elif kind == "code":
        text = " ".join(content.get("source", "").split())
    else:
        text = ""
    return text[:limit] + ("…" if len(text) > limit else "")


KIND_LABEL = {"link": "Link", "note": "Note", "text": "Text", "code": "Code", "image": "Image"}

# Structure, not English: a call, an assignment, or a declaration. "print the poster" stays prose.
_CODE_LINE = re.compile(
    r"[A-Za-z_][\w.]*\s*\("
    r"|[A-Za-z_][\w]*\s*=\s*[^=\s]"
    r"|[{};]"
    r"|^(?:def|class|function|fn|const|let|var)\s+\w"
    r"|^(?:import|from)\s+[\w.]+(?:\s+import\s+[\w*., ]+)?\s*$"
)


def looks_like_code(text: str) -> bool:
    """True when plain text or a note is source code that was never saved as a code card."""
    if any(block.strip() for block in re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)):
        return True
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("```")]
    if not lines:
        return False
    hits = sum(1 for ln in lines if _CODE_LINE.search(ln) and not (len(ln.split()) > 8 and ln.endswith(".")))
    if len(lines) == 1:
        return hits == 1 and len(lines[0]) <= 180
    return hits >= 2 and hits / len(lines) >= 0.34
