"""Tests for the `{ ... }` pair-dispatch immediate words.

Semantics:
- Body is a sequence of tokens between `{` and `}`.
- Even count: all pairs (key, action). No default.
- Odd count: leading pairs plus a trailing default.
- Each pair compiles to `dup key = if drop action branch->end then` —
  case-val is always consumed on every code path.
- Default (or implicit drop if absent) runs on fall-through.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import CompileError, compile_and_run


class TestBraceDispatchValueMapping:
    """Pure value mapping: each action pushes a literal."""

    @pytest.mark.parametrize("input_value,expected", [
        (1, 100),
        (2, 200),
        (3, 300),
    ])
    def test_each_pair_matches_to_literal(self, input_value, expected):
        src = f"""
        : classify {{  1 100  2 200  3 300  -1 }} ;
        : main {input_value} classify halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"key {input_value} should map to value {expected}"
        )

    def test_leftover_token_is_default_value(self):
        src = """
        : classify {  1 100  2 200  -1 } ;
        : main 42 classify halt ;
        """
        result = compile_and_run(src)
        assert result == [0xFFFF], (
            "fall-through default -1 should be returned (as unsigned 0xFFFF)"
        )

    def test_first_match_wins(self):
        src = """
        : classify {  1 100  1 999  -1 } ;
        : main 1 classify halt ;
        """
        assert compile_and_run(src) == [100], (
            "first matching pair should win"
        )


class TestBraceDispatchConsumesCaseValue:
    """{ } guarantees case-val is consumed in every path."""

    def test_match_consumes_case_value(self):
        src = """
        : classify {  1 100  2 200 } ;
        : main 7 1 classify halt ;
        """
        assert compile_and_run(src) == [7, 100], (
            "after match, case-val (1) should be gone, leaving 7 below 100"
        )

    def test_fall_through_consumes_case_value(self):
        src = """
        : classify {  1 100  2 200 } ;
        : main 7 42 classify halt ;
        """
        assert compile_and_run(src) == [7], (
            "after fall-through with no default, case-val should be gone"
        )

    def test_default_replaces_case_value(self):
        src = """
        : classify {  1 100  2 200  -1 } ;
        : main 7 42 classify halt ;
        """
        assert compile_and_run(src) == [7, 0xFFFF], (
            "default replaces case-val cleanly — no extra drop needed"
        )


class TestBraceDispatchSideEffects:
    """Actions can be word names that do side effects."""

    def test_dispatch_to_named_actions(self):
        src = """
        variable seen
        : do-one    1 seen ! ;
        : do-two    2 seen ! ;
        : do-three  3 seen ! ;
        : do-other  99 seen ! ;
        : classify {  1 do-one  2 do-two  3 do-three  do-other } ;
        """
        for n, expected in [(1, 1), (2, 2), (3, 3), (42, 99)]:
            r = compile_and_run(src + f": main {n} classify seen @ halt ;")
            assert r == [expected], (
                f"input {n} should set seen to {expected}, got {r}"
            )

    def test_no_default_just_drops(self):
        src = """
        variable seen
        : do-one  1 seen ! ;
        : do-two  2 seen ! ;
        : classify {  1 do-one  2 do-two } ;
        : main 99 seen !  42 classify  seen @ halt ;
        """
        assert compile_and_run(src) == [99], (
            "fall-through with no default should not run any action; "
            "seen should remain 99"
        )


class TestBraceDispatchKeyTypes:

    def test_named_constant_as_key(self):
        src = """
        110 constant key-n
        115 constant key-s
        variable seen
        : do-n  1 seen ! ;
        : do-s  2 seen ! ;
        : f {  key-n do-n  key-s do-s  drop 0 seen ! } ;
        : main 115 f seen @ halt ;
        """
        assert compile_and_run(src) == [2], (
            "constant name should resolve to its value as the key"
        )

    def test_negative_keys(self):
        src = """
        : f {  -1 100  -2 200  0 } ;
        : main -2 f halt ;
        """
        assert compile_and_run(src) == [200], (
            "negative literal keys should match correctly"
        )

    def test_hex_keys(self):
        src = """
        : f {  $0a 10  $14 20  -1 } ;
        : main $14 f halt ;
        """
        assert compile_and_run(src) == [20], (
            "hex literal keys should work"
        )


class TestBraceDispatchEmpty:

    def test_empty_braces_just_drops_case_value(self):
        src = """
        : f { } ;
        : main 7 42 f halt ;
        """
        assert compile_and_run(src) == [7], (
            "empty { } should just drop the case-val"
        )

    def test_only_default_runs_default(self):
        src = """
        : f { 999 } ;
        : main 42 f halt ;
        """
        assert compile_and_run(src) == [999], (
            "single token between braces is treated as default"
        )


class TestBraceDispatchStructuralErrors:

    def test_unclosed_brace_raises(self):
        src = ": bad {  1 100 ;  : main 42 bad halt ;"
        with pytest.raises(CompileError, match="without matching"):
            compile_and_run(src)

    def test_lone_closing_brace_raises(self):
        src = ": bad } ;  : main bad halt ;"
        with pytest.raises(CompileError, match="without matching"):
            compile_and_run(src)

    def test_brace_in_interpret_state_raises(self):
        src = "{ 1 2 }  : main halt ;"
        with pytest.raises(CompileError, match="only works inside"):
            compile_and_run(src)


class TestBraceDispatchManyArms:

    @pytest.mark.parametrize("n,expected", [
        (0, 1000),
        (1, 1001),
        (2, 1002),
        (3, 1003),
        (4, 1004),
        (5, 1005),
        (6, 1006),
        (7, 1007),
        (42, 9999),
    ])
    def test_eight_arm_dispatch_with_default(self, n, expected):
        src = f"""
        : f {{
            0 1000  1 1001  2 1002  3 1003
            4 1004  5 1005  6 1006  7 1007
            9999
        }} ;
        : main {n} f halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"input {n} should dispatch to {expected}"
        )


class TestBraceDispatchNested:

    @pytest.mark.parametrize("outer,inner,expected", [
        (1, 10, 11),
        (1, 20, 12),
        (2, 10, 21),
        (2, 20, 22),
        (1, 99, 99),
        (3,  0, 99),
    ])
    def test_nested_dispatch_matrix(self, outer, inner, expected):
        src = f"""
        variable seen
        : set-11  11 seen ! ;
        : set-12  12 seen ! ;
        : set-21  21 seen ! ;
        : set-22  22 seen ! ;
        : set-99  99 seen ! ;
        : sub-1   {{  10 set-11  20 set-12  set-99 }} ;
        : sub-2   {{  10 set-21  20 set-22  set-99 }} ;
        : drop99  drop set-99 ;
        : top     swap {{  1 sub-1  2 sub-2  drop99 }} ;
        : main {outer} {inner} top seen @ halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"nested dispatch ({outer}, {inner}) should set seen to {expected}"
        )


class TestBraceDispatchInsideDoubleColon:
    """:: should be able to inline { } since it only uses standard primitives."""

    def test_brace_works_in_force_inline(self):
        src = """
        :: tagged  {  1 100  2 200  -1 } ;
        : main 1 tagged halt ;
        """
        assert compile_and_run(src) == [100], (
            "{ } should work inside :: definitions because it only uses "
            "standard inlinable primitives (over, =, drop) and branches"
        )
