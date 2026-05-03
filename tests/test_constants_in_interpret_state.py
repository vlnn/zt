"""
Tests for constants evaluating in interpret state.

A `constant` definition stashes its value on the Word, and `_interpret_token`
looks up known constants and pushes their value to the host stack — making
constants composable with directives like `,`, `allot`, and another `constant`.

This is the foundation Phase 2's `--` directive builds on.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError, Word, compile_and_run


def make_compiler(origin: int = 0x8000) -> Compiler:
    return Compiler(origin=origin, inline_primitives=False, inline_next=False)


class TestConstantValueStashedOnWord:

    def test_constant_word_has_value_field(self):
        c = make_compiler()
        c.compile_source("42 constant n : main halt ;")
        assert c.words["n"].value == 42, (
            "constant Word should stash its host-stack value as `value`"
        )

    def test_zero_constant_stashes_zero(self):
        c = make_compiler()
        c.compile_source("0 constant zero : main halt ;")
        assert c.words["zero"].value == 0, (
            "value=0 should be stashed (must use `is not None`, not truthiness)"
        )

    def test_negative_constant_preserves_sign(self):
        c = make_compiler()
        c.compile_source("-1 constant minus-one : main halt ;")
        assert c.words["minus-one"].value == -1, (
            "negative constants should keep Python signedness on the Word"
        )

    @pytest.mark.parametrize("source,name,expected", [
        ("42 constant n",        "n",     42),
        ("$ff constant mask",    "mask",  0xff),
        ("$1234 constant addr",  "addr",  0x1234),
        ("0 constant zero",      "zero",  0),
        ("-1 constant neg",      "neg",   -1),
    ], ids=["decimal", "hex_byte", "hex_word", "zero", "negative"])
    def test_value_matches_source_literal(self, source, name, expected):
        c = make_compiler()
        c.compile_source(f"{source} : main halt ;")
        assert c.words[name].value == expected, (
            f"{source!r} should stash {expected} on the Word"
        )

    def test_variable_has_no_value(self):
        c = make_compiler()
        c.compile_source("variable v : main halt ;")
        assert c.words["v"].value is None, (
            "variables shouldn't get a stashed value (only constants do)"
        )

    def test_create_word_has_no_value(self):
        c = make_compiler()
        c.compile_source("create x : main halt ;")
        assert c.words["x"].value is None, (
            "create-words shouldn't get a stashed value (only constants do)"
        )


class TestConstantPushesInInterpretState:

    def test_constant_used_with_comma(self):
        result = compile_and_run(
            "42 constant n  create tbl n , : main tbl @ halt ;"
        )
        assert result == [42], (
            "`n ,` in interpret state should push n's value, then , should consume it"
        )

    def test_constant_used_with_allot(self):
        c = make_compiler()
        c.compile_source(
            "8 constant /thing  create buf /thing allot : main halt ;"
        )
        c.compile_main_call()
        c.build()
        before = c.words["buf"].data_address
        assert before is not None, "create should set a data_address on buf"

    def test_constant_used_to_define_another_constant(self):
        result = compile_and_run(
            "5 constant a  a constant b : main b halt ;"
        )
        assert result == [5], (
            "`a constant b` should treat a's value as the new constant's value"
        )

    def test_constant_chain_three_deep(self):
        result = compile_and_run(
            "7 constant a  a constant b  b constant c : main c halt ;"
        )
        assert result == [7], (
            "transitively-defined constants should preserve the original value"
        )

    def test_zero_constant_evaluates_in_interpret_state(self):
        result = compile_and_run(
            "0 constant zero  create x zero , : main x @ halt ;"
        )
        assert result == [0], (
            "value=0 should still push (Phase 1 must use `is not None`)"
        )

    def test_negative_constant_evaluates_in_interpret_state(self):
        result = compile_and_run(
            "-1 constant neg  create x neg , : main x @ halt ;"
        )
        assert result == [0xFFFF], (
            "-1 should round-trip as 0xFFFF (cell is 16-bit unsigned at runtime)"
        )

    def test_hex_constant_evaluates_in_interpret_state(self):
        result = compile_and_run(
            "$1234 constant addr  create x addr , : main x @ halt ;"
        )
        assert result == [0x1234], "hex literal should round-trip via constant"


class TestNonConstantsStillFailInInterpretState:

    def test_variable_in_interpret_state_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected word 'v'"):
            c.compile_source("variable v  v create x : main halt ;")

    def test_create_word_in_interpret_state_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected word 'x'"):
            c.compile_source("create x  x create y : main halt ;")

    def test_unknown_word_in_interpret_state_still_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected word 'nope'"):
            c.compile_source("nope : main halt ;")

    def test_primitive_in_interpret_state_still_raises(self):
        c = make_compiler()
        with pytest.raises(CompileError, match="unexpected word"):
            c.compile_source("42 + : main halt ;")


class TestCompileStateRegressions:

    def test_constant_in_colon_body_still_emits_push(self):
        result = compile_and_run("42 constant n : main n halt ;")
        assert result == [42], (
            "regression: constants must still push their value when used in compile state"
        )

    def test_constant_used_twice_in_colon_body(self):
        result = compile_and_run(
            "10 constant ten : main ten ten + halt ;"
        )
        assert result == [20], (
            "regression: constant in compile state should still emit a callable pusher"
        )

    @pytest.mark.parametrize("source,expected", [
        ("3 constant n : main n n * n + halt ;", [12]),
        ("$ff constant mask : main mask halt ;", [0xff]),
        ("0 constant z : main z halt ;",         [0]),
    ], ids=["arith", "hex", "zero"])
    def test_compile_state_constant_usage_unchanged(self, source, expected):
        assert compile_and_run(source) == expected, (
            f"regression: {source!r} should still produce {expected}"
        )
