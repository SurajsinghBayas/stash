"""Female voiceover for the explainer videos, spoken by macOS's built-in text to speech (`say`).

The script below drives everything: each line belongs to one scene, the scene lasts as long as its line takes to
say (rounded up to the beat so cuts stay on the music), and the captions are the same words, split into short chunks
timed by length. Install a Premium voice for a far more natural read: System Settings → Accessibility → Spoken
Content → System voice → Manage Voices → English → Ava (Premium) or Zoe (Premium). It is picked up automatically.
"""

import math
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SR = 48_000
VOICES = ["Ava (Premium)", "Zoe (Premium)", "Ava (Enhanced)", "Zoe (Enhanced)", "Samantha (Enhanced)", "Samantha"]
RATE = 178  # words per minute, a touch slower than the default for clarity
LEAD_IN = 0.45  # seconds of picture before the voice starts in each scene
TAIL = 0.7  # breathing room after the line, before the cut
GRID = 0.5  # one beat at 120 BPM; scene starts snap to it


@dataclass
class Line:
    scene: str
    spoken: str  # what the voice says (spelled out for the speech engine where needed)
    shown: str  # what the captions show
    min_len: float = 0.0


SCRIPT = [
    Line("hook", "You save things everywhere. Links, notes, screenshots, code. And when you need them, they're gone.",
         "You save things everywhere. Links, notes, screenshots, code. And when you need them, they're gone."),
    Line("intro", "Meet Stash. One place for everything you save.",
         "Meet Stash. One place for everything you save."),
    Line("canvas", "Drop anything onto your canvas. Links, notes, code and images, side by side, arranged the way "
         "you think.", "Drop anything onto your canvas. Links, notes, code and images, side by side, arranged the "
         "way you think.", 6.0),
    Line("ask", "Looking for something? Just ask. Stash answers from your own cards, and points to each one, so you "
         "know exactly where it came from.", "Looking for something? Just ask. Stash answers from your own cards, "
         "and points to each one, so you know exactly where it came from.", 6.0),
    Line("remind", "Saved something for later? Add a reminder, and Stash emails you right on time, with the card one "
         "tap away.", "Saved something for later? Add a reminder, and Stash emails you right on time, with the card "
         "one tap away.", 6.0),
    Line("end", "Stash is free. Try it today, at stash dot suraj bayas dot me.",
         "Stash is free. Try it today at stash.surajbayas.me", 4.5),
]


def pick_voice() -> str:
    listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True).stdout
    installed = {line.split("  ")[0].strip() for line in listing.splitlines()}
    for name in VOICES:
        if name in installed or any(v.startswith(name + " (") or v == name for v in installed):
            return name
    raise SystemExit("No suitable female English voice found; install Samantha or Ava in System Settings")


def speak(text: str, voice: str, out: Path) -> np.ndarray:
    subprocess.run(["say", "-v", voice, "-r", str(RATE), "--file-format=WAVE", f"--data-format=LEI16@{SR}",
                    "-o", str(out), text], check=True)
    with wave.open(str(out)) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float64) / 32768
        if w.getnchannels() == 2:
            audio = audio.reshape(-1, 2).mean(axis=1)
    # trim the engine's leading and trailing silence so timings are exact
    loud = np.flatnonzero(np.abs(audio) > 0.01)
    return audio[max(0, loud[0] - 480):loud[-1] + 2400] if len(loud) else audio


def chunks(text: str, max_words: int = 8) -> list[str]:
    """Caption-sized pieces. Sentences always break; clauses (at commas) join up while they fit in `max_words`;
    a clause that is still too long splits into even halves, so no caption is left with one stray word."""
    out: list[str] = []
    sentences: list[list[str]] = [[]]
    for word in text.split():
        sentences[-1].append(word)
        if word[-1] in ".?!":
            sentences.append([])
    for sentence in filter(None, sentences):
        clauses: list[list[str]] = [[]]
        for word in sentence:
            clauses[-1].append(word)
            if word.endswith(","):
                clauses.append([])
        cur: list[str] = []
        for clause in filter(None, clauses):
            if cur and len(cur) + len(clause) > max_words:
                out.append(" ".join(cur))
                cur = []
            cur += clause
            while len(cur) > max_words:
                parts = math.ceil(len(cur) / max_words)
                size = math.ceil(len(cur) / parts)
                out.append(" ".join(cur[:size]))
                cur = cur[size:]
        if cur:
            out.append(" ".join(cur))
    return out


@dataclass
class Explainer:
    voice: str
    duration: float
    timeline: list[tuple[str, float, float]]
    captions: list[tuple[float, float, str]]
    track: np.ndarray  # mono voice track, SR Hz, `duration` long


def build() -> Explainer:
    voice = pick_voice()
    with tempfile.TemporaryDirectory() as tmp:
        clips = [speak(line.spoken, voice, Path(tmp) / f"{i}.wav") for i, line in enumerate(SCRIPT)]

    timeline: list[tuple[str, float, float]] = []
    captions: list[tuple[float, float, str]] = []
    placed: list[tuple[float, np.ndarray]] = []
    t = 0.0
    for line, clip in zip(SCRIPT, clips, strict=True):
        talk = len(clip) / SR
        length = math.ceil(max(LEAD_IN + talk + TAIL, line.min_len) / GRID) * GRID
        timeline.append((line.scene, t, t + length))
        start = t + LEAD_IN
        placed.append((start, clip))
        # captions follow the voice, each piece on screen for its share of the line (by characters)
        pieces = chunks(line.shown)
        weights = [len(p) + 6 for p in pieces]
        c = start
        for piece, wgt in zip(pieces, weights, strict=True):
            d = talk * wgt / sum(weights)
            captions.append((round(c, 2), round(c + d, 2), piece))
            c += d
        t += length

    duration = t
    track = np.zeros(int(duration * SR))
    for start, clip in placed:
        i = int(start * SR)
        track[i:i + len(clip)] += clip[: len(track) - i]
    return Explainer(voice, duration, timeline, captions, track)


def write(track: np.ndarray, out: Path) -> None:
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype("<i2").tobytes())


# Voice on top of the music: clean up the voice, duck the music under it, then mix. Loudness is set afterwards.
MIX_FILTER = (
    "[1:a]highpass=f=90,equalizer=f=3000:t=q:w=1.2:g=3,acompressor=threshold=0.1:ratio=3:attack=5:release=120,"
    "aformat=channel_layouts=stereo,volume=2.2,asplit=2[v1][v2];"
    "[0:a][v1]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[duck];"
    "[duck]volume=0.28[bed];[bed][v2]amix=inputs=2:normalize=0:duration=first[out]"
)


def mix(music: Path, voice: Path, out: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(music), "-i", str(voice),
                    "-filter_complex", MIX_FILTER, "-map", "[out]", "-ar", str(SR), str(out)], check=True)
