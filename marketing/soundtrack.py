"""An original soundtrack for the Stash videos, synthesised from scratch (no samples, so no licensing questions).

120 BPM in A minor (Am, F, C, G). The hook is pads and a riser, the beat drops on the first product scene, and the
end card resolves on a sustained C chord. Sound effects follow the animation: a whoosh on each scene cut, a soft pop
when a card lands, a blip for citation badges and a chime when the reminder notification arrives.
"""

import wave
from pathlib import Path

import numpy as np

SR = 48_000
BPM = 120
BEAT = 60 / BPM
BAR = BEAT * 4
rng = np.random.default_rng(7)

# (pad/arp notes, bass note) as MIDI numbers
CHORDS = [([57, 60, 64, 69], 45), ([53, 57, 60, 65], 41), ([60, 64, 67, 72], 48), ([55, 59, 62, 67], 43)]
END_CHORD = ([60, 64, 67, 71, 76], 36)  # Cmaj7 over a low C


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def ts(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def smooth(x: np.ndarray, n: int) -> np.ndarray:
    return np.convolve(x, np.ones(n) / n, mode="same")


def noise(dur: float) -> np.ndarray:
    return rng.uniform(-1, 1, int(dur * SR))


# ---------- instruments (mono) ----------

def kick() -> np.ndarray:
    t = ts(0.4)
    f = 46 + 120 * np.exp(-t / 0.035)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13)
    return body + 0.15 * noise(0.4) * np.exp(-t / 0.003)


def clap() -> np.ndarray:
    t = ts(0.3)
    n = noise(0.3)
    bright = n - smooth(n, 6)
    env = sum(np.exp(-np.clip(t - d, 0, None) / 0.012) * (t >= d) for d in (0, 0.011, 0.022)) * 0.4
    env += np.exp(-t / 0.08) * 0.6
    return bright * env + 0.25 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.04)


def hat(open_: bool = False) -> np.ndarray:
    dur = 0.25 if open_ else 0.06
    t = ts(dur)
    n = noise(dur)
    return (n - smooth(n, 4)) * np.exp(-t / (0.07 if open_ else 0.018))


def bass(note: int, dur: float) -> np.ndarray:
    t = ts(dur)
    f = hz(note)
    sig = sum(np.sin(2 * np.pi * f * k * t) / k * np.exp(-t * k * 2.5) for k in range(1, 9))
    return sig * np.minimum(1, t / 0.006) * np.exp(-t / 0.35)


def pluck(note: int) -> np.ndarray:
    t = ts(0.7)
    f = hz(note)
    sig = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.3 * np.exp(-t * (4 + 3 * k)) for k in range(1, 7))
    return sig * np.minimum(1, t / 0.003)


def pad(notes: list[int], dur: float, detune: float) -> np.ndarray:
    t = ts(dur)
    sig = sum(np.sin(2 * np.pi * hz(n) * (1 + detune) * h * t) * a
              for n in notes for h, a in ((1, 1), (2, 0.25), (3, 0.08)))
    env = np.minimum(1, t / 0.45) * np.minimum(1, (dur - t) / 0.6)
    return sig * env / len(notes)


def bell(f: float) -> np.ndarray:
    t = ts(1.2)
    return sum(np.sin(2 * np.pi * f * r * t) * a * np.exp(-t / d)
               for r, a, d in ((1, 1, 0.5), (2.76, 0.35, 0.18), (5.4, 0.15, 0.08)))


def whoosh(dur: float = 0.7) -> np.ndarray:
    t = ts(dur)
    n = noise(dur)
    band = smooth(n, 5) - smooth(n, 60)
    return band * np.sin(np.pi * t / dur) ** 3


def riser(dur: float) -> np.ndarray:
    t = ts(dur)
    n = noise(dur)
    sweep = np.sin(2 * np.pi * np.cumsum(220 + 700 * (t / dur) ** 2) / SR)
    return ((n - smooth(n, 3)) * 0.6 + sweep * 0.25) * (t / dur) ** 2.5


def pop() -> np.ndarray:
    t = ts(0.09)
    f = 520 + 420 * (1 - np.exp(-t / 0.02))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.025)


def blip() -> np.ndarray:
    t = ts(0.15)
    return np.sin(2 * np.pi * 1320 * t) * np.exp(-t / 0.04) + 0.4 * np.sin(2 * np.pi * 1980 * t) * np.exp(-t / 0.02)


def tick() -> np.ndarray:
    t = ts(0.12)
    return np.sin(2 * np.pi * 1150 * t) * np.exp(-t / 0.012) + 0.7 * np.sin(2 * np.pi * 150 * t) * np.exp(-t / 0.04)


# ---------- arrangement ----------

class Mix:
    def __init__(self, dur: float):
        self.n = int(dur * SR)
        self.bus = {k: np.zeros((2, self.n)) for k in ("drums", "music", "sfx")}

    def add(self, bus: str, sig: np.ndarray, at: float, gain: float, pan: float = 0.0) -> None:
        i = int(at * SR)
        if i >= self.n:
            return
        sig = sig[: self.n - i] * gain
        left, right = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
        self.bus[bus][0, i:i + len(sig)] += sig * left * 1.41
        self.bus[bus][1, i:i + len(sig)] += sig * right * 1.41


def render(duration: float, cuts: list[float], events: list[tuple[float, str]], out: Path) -> None:
    """`cuts`: scene start times (the first is the hook). `events`: (time, animation kind) from the video."""
    drop, last = cuts[1], cuts[-1]
    m = Mix(duration)
    kicks: list[float] = []
    bars = int(np.ceil(duration / BAR))

    for b in range(bars):
        start = b * BAR
        notes, root = CHORDS[b % 4]
        if start >= last:
            break
        end = min(start + BAR, last)
        m.add("music", pad(notes, end - start + 0.6, -0.003), start, 0.16, -0.5)
        m.add("music", pad(notes, end - start + 0.6, 0.003), start, 0.16, 0.5)
        for i in range(8):
            t = start + i * BEAT / 2
            if t >= last:
                break
            groove = t >= drop
            if groove or i % 2 == 0:  # the hook plays the arp in quarter notes
                arp = notes[[0, 1, 2, 1, 3, 2, 1, 2][i]] + 12
                m.add("music", pluck(arp), t, 0.2 if groove else 0.22, 0.35 if i % 2 else -0.35)
            if groove:
                m.add("music", bass(root, BEAT / 2), t, 0.42)
                if i % 2 == 0:
                    m.add("drums", kick(), t, 0.95)
                    kicks.append(t)
                else:
                    m.add("drums", hat(open_=i == 7), t, 0.16, 0.3)
                if i in (2, 6):
                    m.add("drums", clap(), t, 0.42, -0.05)
                m.add("drums", hat(), t + BEAT / 4, 0.06, -0.3)
            elif start >= BAR:  # second bar of the hook: quiet ticking hats build tension
                m.add("drums", hat(), t + BEAT / 4, 0.05 + 0.01 * i, 0.3)

    # end card: one big hit, then a sustained chord that fades out
    notes, root = END_CHORD
    tail = duration - last
    m.add("drums", kick(), last, 1.0)
    kicks.append(last)
    m.add("drums", hat(open_=True), last, 0.2)
    m.add("music", pad(notes, tail + 0.6, -0.003), last, 0.24, -0.5)
    m.add("music", pad(notes, tail + 0.6, 0.003), last, 0.24, 0.5)
    m.add("music", bass(root, tail) * np.exp(-ts(tail) / 0.8) * 2.2, last, 0.45)
    for i, n in enumerate([72, 76, 79, 84]):
        m.add("music", pluck(n), last + 0.25 + i * BEAT / 2, 0.17, (-0.4, 0.4)[i % 2])

    # sound effects
    m.add("sfx", riser(1.4), drop - 1.4, 0.28)
    for c in cuts[1:]:
        m.add("sfx", whoosh(), c - 0.4, 0.5)
    for at, kind in events:
        if kind == "drop" and at < drop:
            m.add("sfx", tick(), at + 0.25, 0.22, rng.uniform(-0.5, 0.5))
        elif kind == "drop":  # the reminder notification
            m.add("sfx", bell(hz(83)), at + 0.15, 0.18, 0.15)
            m.add("sfx", bell(hz(88)), at + 0.29, 0.18, 0.15)
        elif kind == "pop":
            m.add("sfx", pop(), at + 0.05, 0.16, rng.uniform(-0.4, 0.4))
        elif kind == "badge":
            m.add("sfx", blip(), at + 0.08, 0.14)

    # sidechain: music ducks under each kick, which gives the pumping feel
    duck = np.ones(m.n)
    for k in kicks:
        i = int(k * SR)
        t = ts(0.3)[: m.n - i]
        duck[i:i + len(t)] = np.minimum(duck[i:i + len(t)], 1 - 0.55 * np.exp(-t / 0.09))
    mix = m.bus["drums"] + m.bus["music"] * duck + m.bus["sfx"]

    fade = np.minimum(1, (duration - ts(duration)[: m.n]) / 0.9)
    mix = np.tanh(mix * fade * 1.3) / np.tanh(1.3)
    mix /= max(1e-9, np.abs(mix).max()) / 0.89

    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32767).astype("<i2").tobytes())
