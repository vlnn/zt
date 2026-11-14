"""
Tests for the native backend's whole-program analysis: which colon words can be
re-entered while active, and which calling convention each word gets.
"""
from __future__ import annotations

import pytest

from zt.compile.ir import Branch, ColonRef, Label, Literal, PrimRef
from zt.compile.native.analysis import (
    Convention,
    choose_conventions,
    reentrant_words,
)

EXIT = PrimRef("exit")


def _makes_call(cell) -> bool:
    return isinstance(cell, ColonRef) or cell in (PrimRef("execute"), PrimRef("*"))


BODIES = {
    "square": [PrimRef("dup"), PrimRef("*"), EXIT],
    "inc": [PrimRef("1+"), EXIT],
    "twice": [ColonRef("inc"), ColonRef("inc"), EXIT],
    "fact": [PrimRef("dup"), ColonRef("fact"), EXIT],
    "apply": [PrimRef("execute"), EXIT],
    "map": [ColonRef("apply"), EXIT],
    "uses-fact": [ColonRef("fact"), EXIT],
    "tick": [ColonRef("inc"), EXIT],
    "main": [ColonRef("twice"), ColonRef("map"), EXIT],
}


class TestReentrantWords:

    @pytest.mark.parametrize("name,reason", [
        ("fact", "it calls itself"),
        ("apply", "it contains EXECUTE"),
        ("map", "it reaches EXECUTE through apply"),
        ("main", "it reaches EXECUTE through map"),
    ])
    def test_word_that_can_be_reentered_is_flagged(self, name, reason):
        assert name in reentrant_words(BODIES), \
            f"{name!r} should be flagged as re-entrant because {reason}"

    @pytest.mark.parametrize("name,reason", [
        ("inc", "it calls nothing"),
        ("twice", "it only calls plain words"),
        ("uses-fact", "calling a recursive word does not make the caller recursive"),
    ])
    def test_word_that_cannot_be_reentered_is_not_flagged(self, name, reason):
        assert name not in reentrant_words(BODIES), \
            f"{name!r} should not be flagged because {reason}"

    @pytest.mark.parametrize("name", ["tick", "inc"])
    def test_words_reachable_from_interrupt_entry_are_flagged(self, name):
        flagged = reentrant_words(BODIES, interrupt_entries=["tick"])
        assert name in flagged, \
            f"{name!r} can run inside the interrupt handler and should be flagged"

    def test_words_not_reachable_from_interrupt_entry_stay_unflagged(self):
        flagged = reentrant_words(BODIES, interrupt_entries=["tick"])
        assert "twice" not in flagged, \
            "'twice' is not reachable from the handler and should stay unflagged"

    def test_cycle_through_redefined_name_is_flagged(self):
        bodies = {"a": [ColonRef("b"), EXIT], "b": [ColonRef("a"), EXIT]}
        assert reentrant_words(bodies) == {"a", "b"}, \
            "words in a call-graph cycle should both be flagged"

    def test_unknown_interrupt_entry_is_ignored(self):
        assert "ghost" not in reentrant_words(BODIES, interrupt_entries=["ghost"]), \
            "an entry that is not a colon word should not be invented"


class TestChooseConventions:

    @pytest.fixture
    def conventions(self):
        return choose_conventions(BODIES, _makes_call, reentrant_words(BODIES))

    @pytest.mark.parametrize("name,expected,reason", [
        ("inc", Convention.LEAF, "it calls nothing"),
        ("square", Convention.STATIC, "it calls an out-of-line primitive"),
        ("twice", Convention.STATIC, "it calls colons and cannot be re-entered"),
        ("uses-fact", Convention.STATIC, "it cannot be re-entered itself"),
        ("fact", Convention.FRAME, "it is recursive"),
        ("apply", Convention.FRAME, "it contains EXECUTE"),
        ("map", Convention.FRAME, "it reaches EXECUTE"),
    ])
    def test_convention_matches_word_shape(self, conventions, name, expected, reason):
        assert conventions[name] is expected, \
            f"{name!r} should use the {expected.value} convention because {reason}"

    def test_leaf_stays_leaf_even_when_reentrant(self):
        chosen = choose_conventions(BODIES, _makes_call, frozenset({"inc"}))
        assert chosen["inc"] is Convention.LEAF, \
            "a leaf keeps its return address in IX, so re-entrancy should not demote it"

    def test_branches_and_literals_do_not_break_leafness(self):
        bodies = {"clamp": [
            Literal(0), PrimRef("max"),
            Branch("0branch", Label(1)), Label(1), EXIT,
        ]}
        chosen = choose_conventions(bodies, _makes_call, frozenset())
        assert chosen["clamp"] is Convention.LEAF, \
            "inline control flow and literals should keep a word a leaf"
