from __future__ import annotations

import json
from pathlib import Path

import pytest

from zt.profile import ProfileEntry, ProfileReport
from zt.profile_io import (
    DiffEntry,
    ZPROF_VERSION,
    diff_reports,
    read_zprof,
    regressions,
    write_zprof,
)


def _make_report(entries: list[dict], total_ticks: int = 0, total_t_states: int = 0) -> ProfileReport:
    return ProfileReport(
        entries=tuple(
            ProfileEntry(
                word=e["word"],
                calls=e.get("calls", 1),
                ticks=e.get("ticks", 1),
                t_states=e.get("self_t_states", 0),
                incl_t_states=e.get("incl_t_states", 0),
            )
            for e in entries
        ),
        total_ticks=total_ticks or sum(e.get("ticks", 1) for e in entries),
        total_t_states=total_t_states or sum(e.get("self_t_states", 0) for e in entries),
    )


class TestWriteZprof:

    def test_writes_json(self, tmp_path: Path):
        report = _make_report([{"word": "DUP", "self_t_states": 11, "incl_t_states": 11}])
        path = tmp_path / "out.zprof"
        write_zprof(path, report)
        data = json.loads(path.read_text())
        assert data["version"] == ZPROF_VERSION, "written zprof should declare current version"

    def test_entries_have_expected_keys(self, tmp_path: Path):
        report = _make_report([{"word": "DUP", "calls": 3, "ticks": 6,
                                "self_t_states": 11, "incl_t_states": 42}])
        path = tmp_path / "out.zprof"
        write_zprof(path, report)
        entry = json.loads(path.read_text())["entries"][0]
        for key in ("word", "calls", "ticks", "self_t_states", "incl_t_states"):
            assert key in entry, f"entry should contain {key!r}"

    def test_preserves_totals(self, tmp_path: Path):
        report = _make_report(
            [{"word": "A", "self_t_states": 5}],
            total_ticks=100, total_t_states=500,
        )
        path = tmp_path / "out.zprof"
        write_zprof(path, report)
        data = json.loads(path.read_text())
        assert data["total_ticks"] == 100, "total_ticks should round-trip"
        assert data["total_t_states"] == 500, "total_t_states should round-trip"


class TestReadZprof:

    def test_roundtrip(self, tmp_path: Path):
        original = _make_report(
            [{"word": "DUP", "calls": 3, "ticks": 6,
              "self_t_states": 11, "incl_t_states": 42}],
            total_ticks=6, total_t_states=11,
        )
        path = tmp_path / "out.zprof"
        write_zprof(path, original)
        loaded = read_zprof(path)
        assert loaded == original, "write-then-read should round-trip a report"

    def test_rejects_unknown_version(self, tmp_path: Path):
        path = tmp_path / "bad.zprof"
        path.write_text(json.dumps({"version": 99, "total_ticks": 0, "entries": []}))
        with pytest.raises(ValueError, match="unsupported zprof version"):
            read_zprof(path)


class TestDiffReports:

    def test_new_word_in_current_only(self):
        base = _make_report([])
        curr = _make_report([{"word": "NEW", "incl_t_states": 50}])
        diffs = diff_reports(base, curr)
        assert len(diffs) == 1, "should have one diff entry"
        d = diffs[0]
        assert d.base_incl is None, "word absent from baseline should have None base"
        assert d.curr_incl == 50, "current should report the new word's incl t-states"
        assert d.delta is None, "delta is undefined when baseline is missing"

    def test_missing_word_in_current_only(self):
        base = _make_report([{"word": "GONE", "incl_t_states": 30}])
        curr = _make_report([])
        d = diff_reports(base, curr)[0]
        assert d.base_incl == 30, "baseline value should be preserved"
        assert d.curr_incl is None, "missing word in current should have None curr"
        assert d.delta is None, "delta is undefined when current is missing"

    def test_common_word_delta_and_pct(self):
        base = _make_report([{"word": "HOT", "incl_t_states": 100}])
        curr = _make_report([{"word": "HOT", "incl_t_states": 120}])
        d = diff_reports(base, curr)[0]
        assert d.delta == 20, "delta should be curr - base"
        assert d.pct == pytest.approx(20.0), "pct should be 20%"

    def test_negative_delta_for_improvement(self):
        base = _make_report([{"word": "HOT", "incl_t_states": 100}])
        curr = _make_report([{"word": "HOT", "incl_t_states": 75}])
        d = diff_reports(base, curr)[0]
        assert d.delta == -25, "improvement should produce negative delta"
        assert d.pct == pytest.approx(-25.0), "improvement should produce negative pct"

    def test_entries_sorted_by_absolute_delta(self):
        base = _make_report([
            {"word": "SMALL", "incl_t_states": 10},
            {"word": "BIG",   "incl_t_states": 100},
        ])
        curr = _make_report([
            {"word": "SMALL", "incl_t_states": 15},
            {"word": "BIG",   "incl_t_states": 80},
        ])
        diffs = diff_reports(base, curr)
        words = [d.word for d in diffs]
        assert words == ["BIG", "SMALL"], (
            "entries should be sorted by absolute delta descending"
        )


class TestRegressions:

    def test_returns_only_words_exceeding_threshold(self):
        base = _make_report([
            {"word": "SLOW",  "incl_t_states": 100},
            {"word": "FAST",  "incl_t_states": 100},
        ])
        curr = _make_report([
            {"word": "SLOW",  "incl_t_states": 120},
            {"word": "FAST",  "incl_t_states": 100},
        ])
        diffs = diff_reports(base, curr)
        regs = regressions(diffs, threshold_pct=10.0)
        assert [r.word for r in regs] == ["SLOW"], (
            "only SLOW (20% regression) should be flagged over a 10% threshold"
        )

    def test_threshold_is_strict(self):
        base = _make_report([{"word": "EDGE", "incl_t_states": 100}])
        curr = _make_report([{"word": "EDGE", "incl_t_states": 110}])
        diffs = diff_reports(base, curr)
        assert regressions(diffs, threshold_pct=10.0) == [], (
            "exactly-threshold change should not count as regression"
        )
        assert regressions(diffs, threshold_pct=9.9) != [], (
            "change just over threshold should count"
        )

    def test_selected_filter_limits_scope(self):
        base = _make_report([
            {"word": "A", "incl_t_states": 100},
            {"word": "B", "incl_t_states": 100},
        ])
        curr = _make_report([
            {"word": "A", "incl_t_states": 200},
            {"word": "B", "incl_t_states": 200},
        ])
        diffs = diff_reports(base, curr)
        regs = regressions(diffs, threshold_pct=5.0, selected={"A"})
        assert [r.word for r in regs] == ["A"], (
            "only selected words should contribute to the regression set"
        )

    def test_improvements_are_not_regressions(self):
        base = _make_report([{"word": "HOT", "incl_t_states": 100}])
        curr = _make_report([{"word": "HOT", "incl_t_states": 10}])
        diffs = diff_reports(base, curr)
        assert regressions(diffs, threshold_pct=1.0) == [], (
            "large improvements should never be regressions"
        )

    def test_missing_baseline_word_is_not_regression(self):
        base = _make_report([])
        curr = _make_report([{"word": "NEW", "incl_t_states": 1000}])
        diffs = diff_reports(base, curr)
        assert regressions(diffs, threshold_pct=1.0) == [], (
            "a newly-added word has no baseline to regress against"
        )
