from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from forth_runner import ForthTestResult, compile_and_run_word


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
