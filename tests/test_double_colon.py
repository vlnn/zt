"""
Tests for `::` — the always-inline defining word. `::` is like `:` except
that compilation errors out loudly when the body cannot be inlined, and
direct self-recursion is rejected up front.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import (
    CompileError,
    build_from_source,
    compile_and_run,
)


class TestDoubleColonHappyPath:

    def test_simple_inlinable_body_compiles(self):
        _, c = build_from_source(":: add1  1 + ;  : main  41 add1 halt ;")
        assert "add1" in c.words, \
            ":: should register its word in the dictionary"
        assert c.words["add1"].force_inline is True, \
            ":: should set force_inline=True on the word"
        assert c.words["add1"].inlined is True, \
            ":: with inlinable body should land as inlined"

    def test_empty_body_is_allowed(self):
        _, c = build_from_source(":: noop ;  : main  42 noop halt ;")
        assert c.words["noop"].force_inline is True, \
            "empty :: body should still mark the word force_inline=True"

    @pytest.mark.parametrize("src,expected", [
        (":: add1    1 + ;       : main  41 add1 halt ;",      [42]),
        (":: double  dup + ;     : main  21 double halt ;",    [42]),
        (":: mask    $0F and ;   : main  $FF mask halt ;",     [0x0F]),
        (":: noop ;              : main  42 noop halt ;",      [42]),
    ])
    def test_inlined_word_runtime_behavior(self, src, expected):
        assert compile_and_run(src) == expected, \
            f"{src!r} should evaluate to {expected}"


class TestDoubleColonMatchesAutoInlinedColon:
    """A `::` word whose body happens to be whitelist-inlinable should
    produce bytes identical to the same body defined with `:`, which the
    auto-inliner picks up on its own."""

    @pytest.mark.parametrize("body", [
        "1 +",
        "dup +",
        "$0F and",
        "dup drop",
        "swap drop",
    ])
    def test_colon_colon_byte_identical_to_colon(self, body):
        img_single, c_single = build_from_source(
            f": foo  {body} ;  : main  foo halt ;"
        )
        img_double, c_double = build_from_source(
            f":: foo  {body} ;  : main  foo halt ;"
        )
        assert c_single.words["foo"].inlined, \
            f"auto-inliner sanity: ': foo {body} ;' should have been inlined"
        assert c_double.words["foo"].inlined, \
            f":: foo {body} ; should end up inlined"
        assert img_single == img_double, \
            f":: with body {body!r} should emit same bytes as auto-inlined :"


class TestDoubleColonRejectsRecursion:

    @pytest.mark.parametrize("src,name", [
        (":: foo  foo ;                    : main halt ;",    "foo"),
        (":: bar  1 + bar ;                : main halt ;",    "bar"),
        (":: baz  dup baz drop ;           : main halt ;",    "baz"),
    ])
    def test_direct_self_recursion_errors(self, src, name):
        with pytest.raises(CompileError) as exc_info:
            build_from_source(src)
        msg = str(exc_info.value)
        assert "recursive ::" in msg, \
            f":: recursion error should mention 'recursive ::', got {msg!r}"
        assert f"'{name}'" in msg, \
            f":: recursion error should quote the word name '{name}', got {msg!r}"


class TestDoubleColonRejectsNonInlinable:

    def test_body_calling_another_colon_errors(self):
        src = ": helper  1 + ;  :: wrapper  helper ;  : main halt ;"
        with pytest.raises(CompileError) as exc_info:
            build_from_source(src)
        msg = str(exc_info.value)
        assert "wrapper" in msg and "cannot be inlined" in msg, \
            f":: calling a non-:: colon should error clearly, got {msg!r}"


class TestDoubleColonControlFlow:
    """Phase 4: `::` definitions can now contain IF/THEN/ELSE,
    BEGIN/AGAIN/UNTIL/WHILE/REPEAT, and DO/LOOP/+LOOP. LEAVE remains
    rejected by agreed scope."""

    @pytest.mark.parametrize("src,expected,desc", [
        (
            ":: abs-inline  dup 0< if negate then ; "
            ": main  -7 abs-inline halt ;",
            [7],
            ":: with IF/THEN should compile and produce abs(-7) = 7",
        ),
        (
            ":: abs-inline  dup 0< if negate then ; "
            ": main  7 abs-inline halt ;",
            [7],
            ":: with IF/THEN positive case should be identity",
        ),
        (
            ":: clamp-zero  dup 0< if drop 0 else 1+ then ; "
            ": main  -3 clamp-zero halt ;",
            [0],
            ":: with IF/ELSE/THEN should pick the negative branch",
        ),
    ], ids=["abs-neg", "abs-pos", "clamp-neg"])
    def test_if_then_else_in_double_colon(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc

    @pytest.mark.parametrize("src,expected,desc", [
        (
            ":: count-down  begin 1- dup 0= until ; "
            ": main  10 count-down halt ;",
            [0],
            "BEGIN/UNTIL inside :: should count down to 0",
        ),
        (
            ":: while-doubler  begin dup 50 < while 2* repeat ; "
            ": main  3 while-doubler halt ;",
            [96],
            "BEGIN/WHILE/REPEAT inside :: should double until ≥ 50",
        ),
    ], ids=["count-down", "while-doubler"])
    def test_begin_family_in_double_colon(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc

    @pytest.mark.parametrize("src,expected,desc", [
        (
            ":: sum-to-n  0 swap 0 do i + loop ; "
            ": main  5 sum-to-n halt ;",
            [10],
            "DO/LOOP inside :: should sum 0..4 = 10",
        ),
        (
            ":: count-by-twos  0 10 0 do 1+ 2 +loop ; "
            ": main  count-by-twos halt ;",
            [5],
            "+LOOP inside :: should count by 2 from 0 to 10 = 5 iterations",
        ),
    ], ids=["sum-to-5", "step-by-2"])
    def test_do_loop_in_double_colon(self, src, expected, desc):
        assert compile_and_run(src) == expected, desc

    def test_leave_inside_double_colon_errors(self):
        src = (
            ":: try-leave  10 0 do i 5 = if leave then loop ; "
            ": main  try-leave halt ;"
        )
        with pytest.raises(CompileError) as exc_info:
            build_from_source(src)
        msg = str(exc_info.value)
        assert "LEAVE" in msg, \
            f"LEAVE inside :: should error mentioning LEAVE, got {msg!r}"
        assert "::" in msg, \
            f"LEAVE inside :: error should reference ::, got {msg!r}"


class TestDoubleColonRedefinitionWarning:

    def test_colon_then_double_colon_warns_about_kind_change(self):
        _, c = build_from_source(
            ": foo  1 + ;  :: foo  1 + ;  : main  41 foo halt ;"
        )
        assert c.warnings, "redefining : as :: should produce a warning"
        warning = c.warnings[-1]
        assert "foo" in warning, \
            f"warning should mention the redefined word, got {warning!r}"
        assert "::" in warning, \
            f"warning should surface the :: kind, got {warning!r}"

    def test_double_colon_then_colon_warns_about_kind_change(self):
        _, c = build_from_source(
            ":: foo  1 + ;  : foo  1 + ;  : main  41 foo halt ;"
        )
        assert c.warnings, "redefining :: as : should produce a warning"
        warning = c.warnings[-1]
        assert "::" in warning, \
            f"warning should surface the previous :: kind, got {warning!r}"

    def test_same_kind_double_colon_redefinition_warns(self):
        _, c = build_from_source(
            ":: foo  1 + ;  :: foo  2 + ;  : main  40 foo halt ;"
        )
        assert c.warnings, "redefining :: as :: should produce a warning"
        warning = c.warnings[-1]
        assert "foo" in warning, \
            f"warning should mention 'foo', got {warning!r}"


class TestDoubleColonState:

    def test_nested_double_colon_definition_errors(self):
        src = ":: outer  :: inner ; ;"
        with pytest.raises(CompileError) as exc_info:
            build_from_source(src)
        msg = str(exc_info.value)
        assert "nested colon" in msg.lower(), \
            f":: inside :: should error on nested colon, got {msg!r}"

    def test_double_colon_inside_colon_definition_errors(self):
        src = ": outer  :: inner ; ;"
        with pytest.raises(CompileError) as exc_info:
            build_from_source(src)
        msg = str(exc_info.value)
        assert "nested colon" in msg.lower() or "unexpected" in msg.lower(), \
            f":: inside : should error, got {msg!r}"
