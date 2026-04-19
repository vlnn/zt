from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from zt.profile import ProfileEntry, ProfileReport


ZPROF_VERSION = 1


@dataclass(frozen=True)
class DiffEntry:
    word: str
    base_incl: int | None
    curr_incl: int | None
    delta: int | None
    pct: float | None


def write_zprof(path: Path, report: ProfileReport) -> None:
    path.write_text(json.dumps(_report_to_dict(report), indent=2) + "\n")


def read_zprof(path: Path) -> ProfileReport:
    data = json.loads(path.read_text())
    return _dict_to_report(data)


def diff_reports(
    baseline: ProfileReport,
    current: ProfileReport,
) -> list[DiffEntry]:
    base = _by_word(baseline)
    curr = _by_word(current)
    all_words = sorted(set(base) | set(curr), key=lambda w: -_sort_key(base.get(w), curr.get(w)))
    return [_diff_entry(w, base.get(w), curr.get(w)) for w in all_words]


def regressions(
    diffs: list[DiffEntry],
    threshold_pct: float,
    selected: set[str] | None = None,
) -> list[DiffEntry]:
    return [
        d for d in diffs
        if _is_regression(d, threshold_pct, selected)
    ]


def _is_regression(d: DiffEntry, threshold_pct: float, selected: set[str] | None) -> bool:
    if selected is not None and d.word not in selected:
        return False
    if d.pct is None:
        return False
    return d.pct > threshold_pct


def _report_to_dict(report: ProfileReport) -> dict:
    return {
        "version": ZPROF_VERSION,
        "total_ticks": report.total_ticks,
        "total_t_states": report.total_t_states,
        "entries": [_entry_to_dict(e) for e in report.entries],
    }


def _entry_to_dict(e: ProfileEntry) -> dict:
    return {
        "word": e.word,
        "calls": e.calls,
        "ticks": e.ticks,
        "self_t_states": e.t_states,
        "incl_t_states": e.incl_t_states,
    }


def _dict_to_report(data: dict) -> ProfileReport:
    _require_supported_version(data)
    entries = tuple(_dict_to_entry(d) for d in data["entries"])
    return ProfileReport(
        entries=entries,
        total_ticks=data["total_ticks"],
        total_t_states=data.get("total_t_states", 0),
    )


def _dict_to_entry(d: dict) -> ProfileEntry:
    return ProfileEntry(
        word=d["word"],
        calls=d["calls"],
        ticks=d["ticks"],
        t_states=d.get("self_t_states", 0),
        incl_t_states=d.get("incl_t_states", 0),
    )


def _require_supported_version(data: dict) -> None:
    v = data.get("version")
    if v != ZPROF_VERSION:
        raise ValueError(
            f"unsupported zprof version {v!r}; this build understands {ZPROF_VERSION}"
        )


def _by_word(report: ProfileReport) -> dict[str, ProfileEntry]:
    return {e.word: e for e in report.entries}


def _sort_key(base: ProfileEntry | None, curr: ProfileEntry | None) -> int:
    b = base.incl_t_states if base else 0
    c = curr.incl_t_states if curr else 0
    return abs(c - b)


def _diff_entry(
    word: str,
    base: ProfileEntry | None,
    curr: ProfileEntry | None,
) -> DiffEntry:
    if base is None or curr is None:
        return DiffEntry(
            word=word,
            base_incl=base.incl_t_states if base else None,
            curr_incl=curr.incl_t_states if curr else None,
            delta=None,
            pct=None,
        )
    delta = curr.incl_t_states - base.incl_t_states
    pct = (100.0 * delta / base.incl_t_states) if base.incl_t_states else 0.0
    return DiffEntry(
        word=word,
        base_incl=base.incl_t_states,
        curr_incl=curr.incl_t_states,
        delta=delta,
        pct=pct,
    )
