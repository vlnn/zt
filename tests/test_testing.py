"""
Tests for `zt.testing`: passing/failing assertions, extra include dirs, `discover_tests`, and `run_tests`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.testing import ForthTestResult, compile_and_run_word


PASSING_SRC = """
include test-lib.fs
: test-plus   3 4 +   7 assert-eq ;
: test-true   1 assert-true ;
: test-false  0 assert-false ;
"""

FAILING_SRC = """
include test-lib.fs
: test-wrong  3 4 +   8 assert-eq ;
: test-true-fails   0 assert-true ;
: test-false-fails  1 assert-false ;
"""


class TestPassingAssertions:

    @pytest.mark.parametrize("word", ["test-plus", "test-true", "test-false"])
    def test_passing_word_reports_no_failure(self, word):
        result = compile_and_run_word(PASSING_SRC, word)
        assert result == ForthTestResult(failed=False), \
            f"{word!r} passes all its assertions and should report failed=False"


class TestFailingAssertions:

    def test_assert_eq_failure_reports_expected_and_actual(self):
        result = compile_and_run_word(FAILING_SRC, "test-wrong")
        assert result.failed is True, "3+4 = 8 should fail"
        assert result.expected == 8, "expected value should be reported as 8"
        assert result.actual == 7, "actual value should be reported as 7"

    def test_assert_true_failure_is_reported(self):
        result = compile_and_run_word(FAILING_SRC, "test-true-fails")
        assert result.failed is True, \
            "assert-true on zero flag should be reported as failure"

    def test_assert_false_failure_is_reported(self):
        result = compile_and_run_word(FAILING_SRC, "test-false-fails")
        assert result.failed is True, \
            "assert-false on non-zero flag should be reported as failure"


class TestRunnerPlumbing:

    def test_missing_test_word_raises(self):
        with pytest.raises(Exception):
            compile_and_run_word(PASSING_SRC, "test-does-not-exist")

    def test_timeout_surfaces_as_error(self):
        infinite_src = """
include test-lib.fs
: test-loop  begin 0 until ;
"""
        with pytest.raises(TimeoutError):
            compile_and_run_word(infinite_src, "test-loop", max_ticks=10_000)


class TestExtraIncludeDirs:

    def test_source_resolves_includes_from_extra_dir(self, tmp_path):
        lib = tmp_path / "mylib.fs"
        lib.write_text(": square dup * ;\n")
        source = """
include test-lib.fs
include mylib.fs
: test-square  5 square  25 assert-eq ;
"""
        result = compile_and_run_word(
            source, "test-square", extra_include_dirs=[tmp_path],
        )
        assert result == ForthTestResult(failed=False), \
            "extra_include_dirs should let sources include siblings in that dir"

    def test_default_cannot_find_user_sources(self, tmp_path):
        lib = tmp_path / "mylib.fs"
        lib.write_text(": square dup * ;\n")
        source = """
include test-lib.fs
include mylib.fs
: test-square  5 square  25 assert-eq ;
"""
        with pytest.raises(Exception):
            compile_and_run_word(source, "test-square")


class TestDiscovery:

    @pytest.fixture
    def project(self, tmp_path):
        (tmp_path / "test_arith.fs").write_text(
            ": test-one 1 1 assert-eq ;\n"
            ": test-two 2 2 assert-eq ;\n"
            ": helper dup + ;\n"
        )
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "test_stack.fs").write_text(
            ": test-three 3 3 assert-eq ;\n"
        )
        (tmp_path / "not_a_test.fs").write_text(": test-x 1 1 assert-eq ;\n")
        return tmp_path

    def test_finds_test_words_in_top_level_file(self, project):
        from zt.testing import discover_tests
        items = list(discover_tests([project]))
        words = [word for _, word in items]
        assert "test-one" in words, "should find first word"
        assert "test-two" in words, "should find second word"

    def test_skips_non_test_words(self, project):
        from zt.testing import discover_tests
        words = [w for _, w in discover_tests([project])]
        assert "helper" not in words, \
            "words without the 'test-' prefix should not be collected"

    def test_recurses_into_subdirectories(self, project):
        from zt.testing import discover_tests
        words = [w for _, w in discover_tests([project])]
        assert "test-three" in words, "should find words in nested directories"

    def test_skips_files_not_matching_test_glob(self, project):
        from zt.testing import discover_tests
        items = list(discover_tests([project]))
        paths = [p.name for p, _ in items]
        assert "not_a_test.fs" not in paths, \
            "only files starting with 'test_' should be collected"

    def test_accepts_single_file_path(self, project):
        from zt.testing import discover_tests
        items = list(discover_tests([project / "test_arith.fs"]))
        assert len(items) == 2, "file path should yield its two test words"
        assert all(p == project / "test_arith.fs" for p, _ in items), \
            "file path should yield only its own words"

    def test_accepts_file_word_spec(self, project):
        from zt.testing import discover_tests
        spec = f"{project / 'test_arith.fs'}::test-two"
        items = list(discover_tests([spec]))
        assert items == [(project / "test_arith.fs", "test-two")], \
            "file::word spec should yield exactly that pair"

    def test_missing_word_in_spec_raises(self, project):
        from zt.testing import discover_tests
        spec = f"{project / 'test_arith.fs'}::test-nonexistent"
        with pytest.raises(Exception, match="test-nonexistent"):
            list(discover_tests([spec]))


class TestRunTests:

    @pytest.fixture
    def project(self, tmp_path):
        (tmp_path / "test_pass.fs").write_text(
            "include test-lib.fs\n"
            ": test-one  1 1 assert-eq ;\n"
            ": test-two  2 2 assert-eq ;\n"
        )
        (tmp_path / "test_fail.fs").write_text(
            "include test-lib.fs\n"
            ": test-broken  3 4 + 8 assert-eq ;\n"
        )
        return tmp_path

    def test_all_pass_returns_empty_failures(self, project):
        from zt.testing import run_tests
        summary = run_tests([project / "test_pass.fs"])
        assert summary.passed == 2, "both test-one and test-two should pass"
        assert summary.failures == [], "no failures expected on passing file"
        assert summary.success is True, "success should be True when nothing failed"

    def test_failure_is_recorded_with_details(self, project):
        from zt.testing import run_tests
        summary = run_tests([project / "test_fail.fs"])
        assert summary.passed == 0, "no tests pass in the failing file"
        assert len(summary.failures) == 1, "exactly one failure expected"
        failure = summary.failures[0]
        assert failure.word == "test-broken", "failure should carry the word name"
        assert failure.result.expected == 8, "expected value should be preserved"
        assert failure.result.actual == 7, "actual value should be preserved"
        assert summary.success is False, "success should be False with a failure"

    def test_stop_on_first_aborts_remaining(self, project):
        from zt.testing import run_tests
        summary = run_tests([project], stop_on_first_failure=True)
        assert len(summary.failures) == 1, \
            "stop_on_first_failure should break out after the first failure"
        assert summary.passed + len(summary.failures) < 3, \
            "should not run every test when stopping early"

    def test_keyword_filter_narrows_selection(self, project):
        from zt.testing import run_tests
        summary = run_tests([project], keyword="one")
        assert summary.passed == 1, "'one' substring should match only test-one"
        assert summary.failures == [], "test-broken does not match 'one'"

    def test_keyword_filter_matches_substring(self, project):
        from zt.testing import run_tests
        summary = run_tests([project], keyword="broken")
        assert len(summary.failures) == 1, "'broken' should select test-broken only"
        assert summary.passed == 0, "nothing else should run under this filter"

    def test_emits_events_for_each_test(self, project):
        from zt.testing import run_tests
        events = []
        run_tests([project], on_result=events.append)
        words = [ev.word for ev in events]
        assert "test-one" in words, "on_result should fire for passing tests"
        assert "test-broken" in words, "on_result should fire for failing tests too"
