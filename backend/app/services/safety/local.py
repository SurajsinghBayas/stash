"""Free, instant first layer: explicit-term list and adult-domain list.

The term list is deliberately short and phrase-based so harmless text passes ("breast cancer screening",
"kill the process on port 4000"). Hate speech and subtler abuse are left to Bedrock Guardrails. Extend
`EXTRA_TERMS_FILE` at deploy time with a maintained list if needed.
"""

import os
import re
import unicodedata
from functools import lru_cache

SEXUAL = [
    "porn", "porno", "pornography", "pornhub", "xxx", "nude", "nudes", "nudity pics", "naked pics", "sex video",
    "sex tape", "sextape", "blowjob", "handjob", "cumshot", "hentai", "milf", "nsfw", "onlyfans", "camgirl",
    "escort service", "deepthroat", "gangbang", "masturbate", "masturbating", "masturbation", "orgasm", "dildo",
    "pussy", "dick pic", "dick pics", "boobs", "tits", "anal sex", "bdsm", "sexting", "erotic", "horny",
]
ABUSE = [
    "fuck you", "fuck off", "kill yourself", "kys", "go die", "piece of shit", "motherfucker", "bitch", "slut",
    "whore", "retard", "shut up you", "you are stupid", "you're stupid", "you idiot", "stupid bot",
]

ADULT_DOMAINS = {
    "pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "redtube.com", "youporn.com", "onlyfans.com",
    "chaturbate.com", "brazzers.com", "stripchat.com", "spankbang.com", "eporner.com", "tube8.com",
    "livejasmin.com", "bongacams.com", "cam4.com", "fansly.com", "rule34.xxx", "nhentai.net",
}
ADULT_TLDS = {"xxx", "porn", "sex", "adult"}

EXTRA_TERMS_FILE = os.environ.get("SAFETY_EXTRA_TERMS_FILE", "")
EXTRA_DOMAINS_FILE = os.environ.get("SAFETY_ADULT_DOMAINS_FILE", "")

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})


def _read_lines(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [line.strip().lower() for line in handle if line.strip() and not line.startswith("#")]


@lru_cache(maxsize=1)
def _pattern() -> tuple[re.Pattern, dict[str, str]]:
    category = {t: "SEXUAL" for t in SEXUAL} | {t: "INSULTS" for t in ABUSE}
    for term in _read_lines(EXTRA_TERMS_FILE):
        category.setdefault(term, "WORDLIST")
    alternatives = sorted((re.escape(t).replace(r"\ ", r"\s+") for t in category), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(alternatives) + r")\b"), category


@lru_cache(maxsize=1)
def _domains() -> set[str]:
    return ADULT_DOMAINS | set(_read_lines(EXTRA_DOMAINS_FILE))


def _variants(text: str) -> list[str]:
    base = unicodedata.normalize("NFKC", text).lower()
    leet = base.translate(_LEET)
    spaced = re.sub(r"[^a-z0-9]+", " ", leet)
    # "p o r n", "p.o.r.n", "p-o-r-n" → "porn": join runs of single letters
    squashed = re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda m: m.group(0).replace(" ", ""), spaced)
    return [re.sub(r"[^a-z0-9]+", " ", base), spaced, squashed]


def match_terms(text: str) -> list[str]:
    pattern, category = _pattern()
    found: set[str] = set()
    for variant in _variants(text):
        for hit in pattern.findall(variant):
            term = re.sub(r"\s+", " ", hit)
            found.add(category.get(term, "WORDLIST"))
    return sorted(found)


def is_adult_domain(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host.rsplit(".", 1)[-1] in ADULT_TLDS:
        return True
    parts = host.split(".")
    return any(".".join(parts[i:]) in _domains() for i in range(len(parts) - 1))
