"""
Tests for `ForthMachine` 128K mode: mode propagation to the inner Z80,
`ForthResult.page_writes` capture, and the 48K default staying byte-identical.
"""
from __future__ import annotations

import pytest

from zt.sim import ForthMachine, ForthResult


class TestModeDefault:

    def test_default_is_48k(self):
        fm = ForthMachine()
        assert fm.mode == "48k", "ForthMachine default mode should be 48K"

    def test_mode_set_to_128k(self):
        fm = ForthMachine(mode="128k")
        assert fm.mode == "128k", "ForthMachine(mode='128k') should record mode"


class TestPageWritesCapture:

    def test_empty_when_no_paging_occurs(self):
        fm = ForthMachine(mode="128k")
        result = fm.run([fm.label("HALT")])
        assert result.page_writes == [], (
            "a program that never writes $7FFD should leave page_writes empty"
        )

    def test_page_writes_field_exists_on_default_result(self):
        fm = ForthMachine()
        result = fm.run([fm.label("HALT")])
        assert result.page_writes == [], (
            "ForthResult.page_writes should default to [] even in 48K mode"
        )


class TestResultDataclass:

    def test_page_writes_defaults_to_empty_list(self):
        result = ForthResult(data_stack=[])
        assert result.page_writes == [], (
            "ForthResult.page_writes should default to an empty list"
        )

    def test_page_writes_accepts_explicit_value(self):
        result = ForthResult(data_stack=[], page_writes=[0x11, 0x14])
        assert result.page_writes == [0x11, 0x14], (
            "ForthResult.page_writes should store the list given at construction"
        )


class TestFortyEightKBehaviourUnchanged:

    @pytest.mark.parametrize("initial_stack,expected_top", [
        ([7], 7),
        ([42], 42),
        ([0xBEEF], 0xBEEF),
    ])
    def test_initial_stack_still_works(self, initial_stack, expected_top):
        fm = ForthMachine()
        result = fm.run([fm.label("HALT")], initial_stack=initial_stack)
        assert result.data_stack[-1] == expected_top, (
            "48K mode with a mode kwarg should still preserve initial stack"
        )
