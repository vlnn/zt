"""End-to-end LilyPond -> AY song-data transcription script.

Reads ../source/bach-invention-04.ly, parses both voices, expands them
onto the 16th-note grid, maps MIDI to AY tone periods, and emits a
`create song ...` Forth definition into ../app/song-data.fs.

Usage (from the repo root):
    uv run python examples/im2-bach/tools/generate_song_data.py
"""
from __future__ import annotations

import re
from pathlib import Path

from transcribe_lilypond import (
    Event,
    PITCH_CLASS,
    parse_voice,
)


HERE = Path(__file__).parent
SOURCE = HERE.parent / "source" / "bach-invention-04.ly"
OUT = HERE.parent / "app" / "song-data.fs"

VOICE_ONE_ANCHOR = 60   # \relative c'  -> middle C (C4) anchor
VOICE_TWO_ANCHOR = 48   # \relative c   -> C3 anchor

AY_CLOCK_HZ = 1_773_400


def midi_to_freq(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def midi_to_period(midi: int | None) -> int:
    if midi is None:
        return 0
    return round(AY_CLOCK_HZ / (16.0 * midi_to_freq(midi)))


def extract_voice_body(src: str, name: str) -> str:
    """Pull the `{...}` body of `voiceone =` or `voicetwo =` out of the .ly."""
    pattern = re.compile(rf"{name}\s*=\s*\\relative\s+\S+\s*\{{(.*?)\n}}", re.DOTALL)
    m = pattern.search(src)
    if not m:
        raise ValueError(f"could not find voice body for {name!r}")
    return m.group(1)


def expand_to_ticks(events: list[Event]) -> list[int | None]:
    """Repeat each event's pitch over its 16th-note span. Tied notes
    of the same pitch as the previous event extend it; rests come
    through as None."""
    ticks: list[int | None] = []
    for ev in events:
        for _ in range(ev.sixteenths):
            ticks.append(ev.midi)
    return ticks


def align_voices(v1: list[int | None], v2: list[int | None]) -> list[tuple[int | None, int | None]]:
    n = max(len(v1), len(v2))
    pad_v1 = v1 + [None] * (n - len(v1))
    pad_v2 = v2 + [None] * (n - len(v2))
    return list(zip(pad_v1, pad_v2))


def format_song_table(steps: list[tuple[int | None, int | None]]) -> str:
    lines: list[str] = []
    lines.append("\\ AUTO-GENERATED from bach-invention-04.ly (Mutopia, Allen Garvin, public domain)")
    lines.append("\\ Each step holds period_a (RH voice) and period_b (LH voice). 0 = rest.")
    lines.append("")
    lines.append(f"{len(steps)} constant song-length")
    lines.append("")
    lines.append("create song")
    chunk = []
    for v1_midi, v2_midi in steps:
        pa = midi_to_period(v1_midi)
        pb = midi_to_period(v2_midi)
        chunk.append(f"{pa:6d} , {pb:6d} ,")
        if len(chunk) == 4:
            lines.append("    " + "  ".join(chunk))
            chunk = []
    if chunk:
        lines.append("    " + "  ".join(chunk))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    src = SOURCE.read_text()
    v1_events = parse_voice(extract_voice_body(src, "voiceone"), anchor_midi=VOICE_ONE_ANCHOR)
    v2_events = parse_voice(extract_voice_body(src, "voicetwo"), anchor_midi=VOICE_TWO_ANCHOR)
    v1_ticks = expand_to_ticks(v1_events)
    v2_ticks = expand_to_ticks(v2_events)
    aligned = align_voices(v1_ticks, v2_ticks)
    OUT.write_text(format_song_table(aligned))
    print(f"wrote {len(aligned)} steps -> {OUT}")


if __name__ == "__main__":
    main()
