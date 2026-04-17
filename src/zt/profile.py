from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


UNKNOWN = "<unknown>"


@dataclass(frozen=True)
class WordRange:
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class ProfileEntry:
    word: str
    calls: int
    ticks: int


@dataclass(frozen=True)
class ProfileReport:
    entries: tuple[ProfileEntry, ...]
    total_ticks: int


def build_word_ranges(
    words: dict[str, int | None],
    code_end: int | None = None,
) -> list[WordRange]:
    addressed = sorted(
        (addr, name) for name, addr in words.items() if addr is not None
    )
    if not addressed:
        return []
    return [
        WordRange(name=name, start=addr, end=_end_of(i, addressed, code_end))
        for i, (addr, name) in enumerate(addressed)
    ]


def _end_of(i: int, addressed: list, code_end: int | None) -> int:
    if i + 1 < len(addressed):
        return addressed[i + 1][0]
    return code_end if code_end is not None else addressed[i][0] + 1


def resolve_word(pc: int, ranges: list[WordRange]) -> str | None:
    if not ranges:
        return None
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    starts = [r.start for r in sorted_ranges]
    idx = bisect_right(starts, pc) - 1
    if idx < 0:
        return None
    r = sorted_ranges[idx]
    return r.name if pc < r.end else None


class Profiler:

    def __init__(self, ranges: list[WordRange]):
        self._ranges = sorted(ranges, key=lambda r: r.start)
        self._starts = [r.start for r in self._ranges]
        self._ticks: dict[str, int] = {}
        self._calls: dict[str, int] = {}
        self._current: str | None = None
        self._stack: list[str] = []

    def sample(self, pc: int) -> None:
        word = self._resolve(pc)
        self._ticks[word] = self._ticks.get(word, 0) + 1
        if word != self._current:
            self._on_transition(word)
            self._current = word

    def report(self) -> ProfileReport:
        entries = tuple(
            ProfileEntry(word=name, calls=self._calls.get(name, 0), ticks=ticks)
            for name, ticks in sorted(
                self._ticks.items(), key=lambda item: -item[1],
            )
        )
        return ProfileReport(entries=entries, total_ticks=sum(self._ticks.values()))

    def _resolve(self, pc: int) -> str:
        if not self._ranges:
            return UNKNOWN
        idx = bisect_right(self._starts, pc) - 1
        if idx < 0:
            return UNKNOWN
        r = self._ranges[idx]
        return r.name if pc < r.end else UNKNOWN

    def _on_transition(self, word: str) -> None:
        if self._stack and self._stack[-1] == word:
            self._stack.pop()
            return
        self._calls[word] = self._calls.get(word, 0) + 1
        if self._current is not None:
            self._stack.append(self._current)


def format_report(report: ProfileReport) -> str:
    header = f"{'Word':<20} {'Calls':>8} {'Ticks':>10} {'Avg':>10} {'%':>6}"
    lines = [header, "-" * len(header)]
    for e in report.entries:
        lines.append(_format_row(e, report.total_ticks))
    return "\n".join(lines)


def _format_row(e: ProfileEntry, total: int) -> str:
    avg = e.ticks // e.calls if e.calls else 0
    pct = (100.0 * e.ticks / total) if total else 0.0
    return f"{e.word:<20} {e.calls:>8} {e.ticks:>10} {avg:>10} {pct:>5.1f}"
