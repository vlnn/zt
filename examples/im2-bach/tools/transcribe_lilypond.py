from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PITCH_CLASS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def pitch_class(name: str) -> int:
    return PITCH_CLASS[name]


def to_sixteenths(dur: str) -> int | None:
    if not dur:
        return None
    dotted = dur.endswith(".")
    base = int(dur.rstrip("."))
    sixteenths = 16 // base
    if dotted:
        sixteenths = sixteenths * 3 // 2
    return sixteenths


@dataclass(frozen=True)
class Note:
    pitch: str
    accidental: int
    octave_modifier: int
    duration: str
    tied: bool


_NOTE_RE = re.compile(
    r"""
    ^([a-g])
    (isis|eses|is|es|s)?
    !?
    ([',]*)
    (\d+\.?)?
    (~)?$
    """,
    re.VERBOSE,
)

_ACCIDENTAL = {None: 0, "is": 1, "es": -1, "s": -1, "isis": 2, "eses": -2}


def parse_note_token(token: str) -> Note:
    m = _NOTE_RE.match(token)
    if not m:
        raise ValueError(f"not a note token: {token!r}")
    name, acc, mods, dur, tie = m.groups()
    if name in {"c", "d", "f", "g"} and acc == "s":
        raise ValueError(f"ambiguous accidental in {token!r}")
    return Note(
        pitch=name,
        accidental=_ACCIDENTAL[acc],
        octave_modifier=mods.count("'") - mods.count(","),
        duration=dur or "",
        tied=bool(tie),
    )


def relative_midi(prev_midi: int, pc: int, octave_modifier: int) -> int:
    base_octave = (prev_midi // 12) * 12
    candidates = [base_octave + pc + d for d in (-12, 0, 12)]
    best = min(candidates, key=lambda c: (abs(c - prev_midi), -c))
    return best + 12 * octave_modifier


_TOKEN_RE = re.compile(r"[a-gr][a-z']*\d*\.?[',]*~?")


def tokenize(src: str):
    cleaned_lines = []
    for line in src.splitlines():
        i = line.find("%")
        if i >= 0:
            line = line[:i]
        cleaned_lines.append(line)
    text = " ".join(cleaned_lines)
    text = re.sub(r'\\key\s+[a-g](?:is|es)?\s+\\\w+', " ", text)
    text = re.sub(r'\\time\s+\d+/\d+', " ", text)
    text = re.sub(r'\\(?:clef|bar)\s+"[^"]*"', " ", text)
    text = re.sub(r'\\[a-zA-Z]+', " ", text)
    text = re.sub(r'"[^"]*"', " ", text)
    text = text.replace("[", " ").replace("]", " ").replace("|", " ")
    text = text.replace("(", " ").replace(")", " ")
    raw = text.split()
    out = []
    i = 0
    while i < len(raw):
        tok = raw[i]
        if i + 1 < len(raw) and raw[i + 1] == "~":
            tok = tok + "~"
            i += 2
        else:
            i += 1
        out.append(tok)
    return out


@dataclass(frozen=True)
class Event:
    midi: int | None
    sixteenths: int
    tied: bool


SILENCE = Event(midi=None, sixteenths=0, tied=False)


def parse_voice(src: str, anchor_midi: int) -> list[Event]:
    events: list[Event] = []
    prev_midi = anchor_midi
    last_dur = 1
    for tok in tokenize(src):
        if tok.startswith("r"):
            d = to_sixteenths(tok[1:].rstrip("~")) or last_dur
            last_dur = d
            events.append(Event(midi=None, sixteenths=d, tied=False))
            continue
        try:
            note = parse_note_token(tok)
        except ValueError:
            continue
        natural = relative_midi(prev_midi, PITCH_CLASS[note.pitch], note.octave_modifier)
        midi = natural + note.accidental
        d = to_sixteenths(note.duration) or last_dur
        last_dur = d
        events.append(Event(midi=midi, sixteenths=d, tied=note.tied))
        prev_midi = natural
    return events


def events_to_ticks(events: list[Event]) -> list[int | None]:
    ticks: list[int | None] = []
    for e in events:
        ticks.extend([e.midi] * e.sixteenths)
    return ticks


AY_CLOCK_HZ = 1_773_447


def midi_to_ay_period(midi: int) -> int:
    freq_hz = 440.0 * 2 ** ((midi - 69) / 12)
    period = round(AY_CLOCK_HZ / (16 * freq_hz))
    return max(1, min(0xFFF, period))


def merge_voices(v1: list[int | None], v2: list[int | None]) -> list[tuple[int, int]]:
    width = max(len(v1), len(v2))
    pad = lambda v: v + [None] * (width - len(v))
    pairs = []
    for a, b in zip(pad(v1), pad(v2)):
        pa = 0 if a is None else midi_to_ay_period(a)
        pb = 0 if b is None else midi_to_ay_period(b)
        pairs.append((pa, pb))
    return pairs
