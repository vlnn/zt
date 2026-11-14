"""
Tests for call-site expansion of small leaf colon words in the native backend.
"""
from __future__ import annotations

import pytest

from zt.compile.ir import Branch, ColonRef, Label, Literal, PrimRef
from zt.compile.native.expand import expand_small_leaves

EXIT = PrimRef("exit")


def _makes_call(cell) -> bool:
    return isinstance(cell, ColonRef) or cell == PrimRef("*")


def _labels(cells) -> list[int]:
    return [c.id for c in cells if isinstance(c, Label)]


class TestExpansion:

    def test_small_leaf_is_pasted_into_caller(self):
        bodies = {
            "inc": [PrimRef("1+"), EXIT],
            "twice": [ColonRef("inc"), ColonRef("inc"), EXIT],
        }
        expanded = expand_small_leaves(bodies, _makes_call)
        assert expanded["twice"] == [PrimRef("1+"), PrimRef("1+"), EXIT], \
            "calls to a small leaf should be replaced by its body without EXIT"

    def test_expansion_chains_through_earlier_words(self):
        bodies = {
            "inc": [PrimRef("1+"), EXIT],
            "twice": [ColonRef("inc"), ColonRef("inc"), EXIT],
            "four": [ColonRef("twice"), ColonRef("twice"), EXIT],
        }
        expanded = expand_small_leaves(bodies, _makes_call)
        assert expanded["four"] == [PrimRef("1+")] * 4 + [EXIT], \
            "a word that became a small leaf should itself be pasted into later callers"

    @pytest.mark.parametrize("callee_body,reason", [
        ([PrimRef("dup"), PrimRef("*"), EXIT], "it calls an out-of-line primitive"),
        ([ColonRef("other"), EXIT], "it calls another colon"),
        ([PrimRef("dup"), Branch("0branch", Label(1)), EXIT, Label(1), EXIT],
         "it has an early EXIT"),
        ([PrimRef("1+")] * 40 + [EXIT], "it is too long"),
    ])
    def test_unsuitable_callee_stays_a_call(self, callee_body, reason):
        bodies = {
            "other": [PrimRef("*"), EXIT],
            "callee": callee_body,
            "caller": [ColonRef("callee"), EXIT],
        }
        expanded = expand_small_leaves(bodies, _makes_call)
        assert expanded["caller"] == [ColonRef("callee"), EXIT], \
            f"callee should stay a call because {reason}"

    def test_self_call_is_never_expanded(self):
        bodies = {"loop": [ColonRef("loop"), EXIT]}
        assert expand_small_leaves(bodies, _makes_call) == bodies, \
            "a recursive call should be left alone"

    def test_cell_limit_is_respected(self):
        bodies = {
            "three": [PrimRef("1+")] * 3 + [EXIT],
            "caller": [ColonRef("three"), EXIT],
        }
        expanded = expand_small_leaves(bodies, _makes_call, cell_limit=3)
        assert expanded["caller"] == [ColonRef("three"), EXIT], \
            "a callee longer than the cell limit should not be pasted"


class TestLabelRenaming:

    BODIES = {
        "abs?": [
            PrimRef("dup"), Branch("0branch", Label(1)),
            PrimRef("negate"), Label(1), EXIT,
        ],
        "caller": [
            Label(2), ColonRef("abs?"), ColonRef("abs?"),
            Branch("branch", Label(2)), EXIT,
        ],
    }

    def test_each_pasted_copy_gets_distinct_labels(self):
        expanded = expand_small_leaves(self.BODIES, _makes_call)
        labels = _labels(expanded["caller"])
        assert len(labels) == len(set(labels)) == 3, \
            "two pasted copies plus the caller's own label should all be distinct"

    def test_pasted_branch_targets_follow_their_label(self):
        expanded = expand_small_leaves(self.BODIES, _makes_call)
        cells = expanded["caller"]
        first_branch = next(c for c in cells if isinstance(c, Branch))
        assert first_branch.target in cells, \
            "a pasted branch should target the renamed label of its own copy"

    def test_callers_own_labels_are_untouched(self):
        expanded = expand_small_leaves(self.BODIES, _makes_call)
        assert expanded["caller"][0] == Label(2), \
            "the caller's own labels should keep their ids"

    def test_callee_body_is_not_mutated(self):
        before = list(self.BODIES["abs?"])
        expand_small_leaves(self.BODIES, _makes_call)
        assert self.BODIES["abs?"] == before, \
            "expansion should not mutate the callee's stored body"
