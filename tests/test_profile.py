from __future__ import annotations

import pytest

from zt.profile import (
    ProfileReport,
    Profiler,
    UNKNOWN,
    WordRange,
    build_word_ranges,
    format_report,
    resolve_word,
)


@pytest.fixture
def ranges():
    return [
        WordRange(name="start", start=0x8000, end=0x8010),
        WordRange(name="dup",   start=0x8010, end=0x8018),
        WordRange(name="main",  start=0x8020, end=0x8040),
    ]


class TestResolveWord:

    @pytest.mark.parametrize("pc,expected", [
        (0x8000, "start"), (0x800F, "start"),
        (0x8010, "dup"),   (0x8017, "dup"),
        (0x8020, "main"),  (0x803F, "main"),
    ])
    def test_pc_inside_range_resolves_to_its_word(self, ranges, pc, expected):
        assert resolve_word(pc, ranges) == expected, \
            f"pc {pc:#06x} should resolve to {expected!r}"

    @pytest.mark.parametrize("pc", [0x7FFF, 0x8018, 0x801F, 0x8040, 0xFFFF])
    def test_pc_in_a_gap_resolves_to_none(self, ranges, pc):
        assert resolve_word(pc, ranges) is None, \
            f"pc {pc:#06x} should not map to any word"

    def test_empty_ranges_always_returns_none(self):
        assert resolve_word(0x8000, []) is None, \
            "resolve on empty ranges should return None"


class TestProfilerSampling:

    def test_single_sample_attributes_one_tick(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000)
        by_word = _by_word(p.report())
        assert by_word["start"].ticks == 1, "one sample in start should yield 1 tick"

    def test_multiple_samples_in_same_word_accumulate(self, ranges):
        p = Profiler(ranges)
        for _ in range(5):
            p.sample(0x8000)
        by_word = _by_word(p.report())
        assert by_word["start"].ticks == 5, "5 samples in start should total 5 ticks"

    def test_samples_across_words_partition_ticks(self, ranges):
        p = Profiler(ranges)
        for pc in [0x8000, 0x8010, 0x8010, 0x8020]:
            p.sample(pc)
        by_word = _by_word(p.report())
        assert by_word["start"].ticks == 1, "one tick should land in start"
        assert by_word["dup"].ticks == 2,   "two ticks should land in dup"
        assert by_word["main"].ticks == 1,  "one tick should land in main"

    def test_pc_outside_any_range_goes_to_unknown(self, ranges):
        p = Profiler(ranges)
        p.sample(0x9000)
        by_word = _by_word(p.report())
        assert by_word[UNKNOWN].ticks == 1, \
            "pc outside all ranges should be attributed to <unknown>"


class TestProfilerCallCounts:

    def test_first_entry_counts_as_one_call(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000)
        assert _by_word(p.report())["start"].calls == 1, \
            "first sample in a word should count as one call"

    def test_staying_in_same_word_does_not_add_calls(self, ranges):
        p = Profiler(ranges)
        for _ in range(5):
            p.sample(0x8000)
        assert _by_word(p.report())["start"].calls == 1, \
            "staying in start should not add more calls"

    def test_returning_to_caller_does_not_add_a_call(self, ranges):
        p = Profiler(ranges)
        for pc in [0x8020, 0x8010, 0x8020]:
            p.sample(pc)
        by_word = _by_word(p.report())
        assert by_word["main"].calls == 1, \
            "returning to main should not count as a new call"
        assert by_word["dup"].calls == 1, "dup should have exactly one call"

    def test_two_separate_calls_into_same_callee(self, ranges):
        p = Profiler(ranges)
        for pc in [0x8020, 0x8010, 0x8020, 0x8010, 0x8020]:
            p.sample(pc)
        by_word = _by_word(p.report())
        assert by_word["dup"].calls == 2, \
            "dup called twice from main should count 2 calls"
        assert by_word["main"].calls == 1, "main should still be one call"

    def test_nested_calls_each_count_once(self, ranges):
        p = Profiler(ranges)
        for pc in [0x8020, 0x8010, 0x8000, 0x8010, 0x8020]:
            p.sample(pc)
        by_word = _by_word(p.report())
        assert by_word["main"].calls == 1,  "main entered once"
        assert by_word["dup"].calls == 1,   "dup entered once across the nest"
        assert by_word["start"].calls == 1, "start entered once"


class TestReportShape:

    def test_entries_sorted_by_ticks_descending(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8020)
        for _ in range(5):
            p.sample(0x8010)
        for _ in range(3):
            p.sample(0x8000)
        words = [e.word for e in p.report().entries]
        assert words == ["dup", "start", "main"], \
            "entries should be sorted by tick count descending"

    def test_total_ticks_sums_all_samples_including_unknown(self, ranges):
        p = Profiler(ranges)
        for pc in [0x8000, 0x8010, 0x8020, 0x9000]:
            p.sample(pc)
        assert p.report().total_ticks == 4, \
            "total_ticks should include samples in <unknown>"

    def test_empty_profiler_has_no_entries_and_zero_total(self, ranges):
        report = Profiler(ranges).report()
        assert report.entries == (), "no samples should yield no entries"
        assert report.total_ticks == 0, "no samples should yield zero total"


class TestBuildWordRanges:

    def test_ranges_sorted_by_start_address(self):
        ranges = build_word_ranges({"a": 0x8020, "b": 0x8000, "c": 0x8010})
        starts = [r.start for r in ranges]
        assert starts == sorted(starts), "ranges should be sorted by start address"

    def test_range_end_equals_next_word_start(self):
        ranges = build_word_ranges({"a": 0x8000, "b": 0x8010, "c": 0x8020})
        assert ranges[0].end == 0x8010, "range a should end where b starts"
        assert ranges[1].end == 0x8020, "range b should end where c starts"

    def test_last_range_uses_code_end_when_provided(self):
        ranges = build_word_ranges({"a": 0x8000}, code_end=0x8100)
        assert ranges[0].end == 0x8100, \
            "last range should extend to code_end when provided"

    def test_words_without_address_are_skipped(self):
        ranges = build_word_ranges({"a": 0x8000, "b": None})
        assert [r.name for r in ranges] == ["a"], \
            "words without an address should be excluded"

    def test_empty_words_gives_empty_ranges(self):
        assert build_word_ranges({}) == [], \
            "empty words dict should yield empty ranges list"


class TestFormatReport:

    def test_header_contains_all_column_titles(self):
        text = format_report(_run_one_sample())
        for col in ["Word", "Calls", "Ticks", "Avg", "%"]:
            assert col in text, f"header should contain column {col!r}"

    def test_body_contains_word_name_and_tick_count(self):
        p = Profiler([WordRange(name="main", start=0x8000, end=0x8010)])
        for _ in range(4):
            p.sample(0x8000)
        text = format_report(p.report())
        assert "main" in text, "word name should appear in the body"
        assert " 4 " in text or "  4" in text or text.rstrip().endswith(" 4"), \
            "tick count should appear in the body"

    def test_percentages_reflect_tick_share(self):
        ranges = [
            WordRange(name="a", start=0x8000, end=0x8010),
            WordRange(name="b", start=0x8010, end=0x8020),
        ]
        p = Profiler(ranges)
        for _ in range(3):
            p.sample(0x8000)
        p.sample(0x8010)
        text = format_report(p.report())
        assert "75.0" in text, "a with 3/4 samples should show 75.0%"
        assert "25.0" in text, "b with 1/4 samples should show 25.0%"


def _by_word(report: ProfileReport) -> dict:
    return {e.word: e for e in report.entries}


def _run_one_sample() -> ProfileReport:
    p = Profiler([WordRange(name="main", start=0x8000, end=0x8010)])
    p.sample(0x8000)
    return p.report()


class TestProfilerCostParameter:

    @pytest.fixture
    def ranges(self):
        return [
            WordRange(name="a", start=0x8000, end=0x8010),
            WordRange(name="b", start=0x8010, end=0x8020),
        ]

    def test_default_cost_is_one(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000)
        entry = _by_word(p.report())["a"]
        assert entry.t_states == 1, "sample() with no cost should default to cost=1"

    def test_cost_accumulates_per_sample(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=4)
        p.sample(0x8000, cost=7)
        entry = _by_word(p.report())["a"]
        assert entry.t_states == 11, "t_states should accumulate the cost arguments"

    def test_cost_and_tick_counters_are_independent(self, ranges):
        p = Profiler(ranges)
        for _ in range(3):
            p.sample(0x8000, cost=10)
        entry = _by_word(p.report())["a"]
        assert entry.ticks == 3, "ticks should count samples regardless of cost"
        assert entry.t_states == 30, "t_states should sum the cost values"

    def test_per_word_cost_partition(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=4)
        p.sample(0x8010, cost=11)
        p.sample(0x8010, cost=7)
        by = _by_word(p.report())
        assert by["a"].t_states == 4, "a should receive its sample cost"
        assert by["b"].t_states == 18, "b should receive the sum of its two sample costs"

    def test_report_total_t_states(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=4)
        p.sample(0x8010, cost=11)
        p.sample(0x9000, cost=5)
        assert p.report().total_t_states == 20, (
            "total_t_states should sum costs across all words including <unknown>"
        )

    def test_unknown_pc_receives_cost_too(self, ranges):
        p = Profiler(ranges)
        p.sample(0x9000, cost=8)
        entry = _by_word(p.report())[UNKNOWN]
        assert entry.t_states == 8, "<unknown> PCs should still accumulate cost"


class TestFormatReportWithTStates:

    def test_header_mentions_t_states(self):
        report = _run_one_sample()
        text = format_report(report)
        assert "T-states" in text, "report header should include a T-states column"

    def test_t_state_percentage_reflects_cost_share(self):
        ranges = [
            WordRange(name="a", start=0x8000, end=0x8010),
            WordRange(name="b", start=0x8010, end=0x8020),
        ]
        p = Profiler(ranges)
        p.sample(0x8000, cost=30)
        p.sample(0x8010, cost=10)
        text = format_report(p.report())
        assert "75.0" in text, "a with 30/40 cost should show 75.0% of T-states"
        assert "25.0" in text, "b with 10/40 cost should show 25.0% of T-states"


class TestInclusiveTStates:

    @pytest.fixture
    def ranges(self):
        return [
            WordRange(name="main",  start=0x8000, end=0x8010),
            WordRange(name="outer", start=0x8010, end=0x8020),
            WordRange(name="inner", start=0x8020, end=0x8030),
        ]

    def test_leaf_word_incl_equals_self(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=5)
        by = _by_word(p.report())
        assert by["main"].incl_t_states == by["main"].t_states, (
            "a word with no callees should have incl_t_states equal to self t_states"
        )

    def test_caller_incl_covers_callee_time(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=3)
        p.sample(0x8010, cost=7)
        p.sample(0x8000, cost=2)
        by = _by_word(p.report())
        assert by["main"].t_states == 5, "main self should be 3+2=5"
        assert by["outer"].t_states == 7, "outer self should be 7"
        assert by["main"].incl_t_states == 12, (
            "main inclusive should be its own time plus outer's time (3+7+2)"
        )
        assert by["outer"].incl_t_states == 7, (
            "outer inclusive should be its own time only (no callees invoked)"
        )

    def test_deeply_nested_incl_times(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=1)
        p.sample(0x8010, cost=2)
        p.sample(0x8020, cost=4)
        p.sample(0x8010, cost=8)
        p.sample(0x8000, cost=16)
        by = _by_word(p.report())
        assert by["inner"].incl_t_states == 4, "inner inclusive is its own 4"
        assert by["outer"].incl_t_states == 2 + 4 + 8, (
            "outer inclusive covers outer-body plus inner's 4"
        )
        assert by["main"].incl_t_states == 1 + 2 + 4 + 8 + 16, (
            "main inclusive covers everything from its span"
        )

    def test_recursion_does_not_double_count(self, ranges):
        p = Profiler(ranges)
        p.sample(0x8000, cost=2)
        p.sample(0x8010, cost=3)
        p.sample(0x8000, cost=5)
        p.sample(0x8010, cost=7)
        by = _by_word(p.report())
        assert by["main"].incl_t_states == 2 + 3 + 5 + 7, (
            "re-entering main via outer should not double-count the cost"
        )
