"""
ForthResult should surface the simulator's interrupt_count so that Forth-level
tests (and Forth assertions in `.fs` test files) can observe how many ULA
interrupts fired during a run.
"""
from __future__ import annotations

import pytest

from zt.sim import ForthMachine, ForthResult


@pytest.fixture
def fm():
    return ForthMachine()


class TestForthResultInterruptCount:

    def test_field_exists_with_zero_default(self):
        result = ForthResult(data_stack=[])
        assert result.interrupt_count == 0, \
            "ForthResult should default interrupt_count to 0"

    def test_zero_when_no_handler_installed(self, fm):
        result = fm.run(["LIT", 1, "LIT", 2, "PLUS"])
        assert result.interrupt_count == 0, \
            "a normal Forth run with no IM 2 handler should report 0 fires"
