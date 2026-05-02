"""Tests for the CASE/OF/ENDOF/ENDCASE immediate words.

Follows ANS Forth semantics:
- After OF matches, the case-selector is dropped and the body runs.
- ENDCASE emits an unconditional drop at run-time which consumes the
  case-selector if no OF matched.
- Default body is conventionally side-effect-only; for value-returning
  defaults, use `drop value exit` to bypass ENDCASE's drop.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import CompileError, compile_and_run


class TestCaseDispatch:

    @pytest.mark.parametrize("input_value,expected", [
        (1, 100),
        (2, 200),
        (3, 300),
    ])
    def test_each_of_arm_matches_and_returns_value(self, input_value, expected):
        src = f"""
        : classify  ( n -- result )
            case
                1 of 100 endof
                2 of 200 endof
                3 of 300 endof
                drop -1 exit
            endcase ;
        : main {input_value} classify halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"case dispatch on {input_value} should yield {expected}"
        )

    def test_value_returning_default_via_exit(self):
        src = """
        : classify
            case
                1 of 100 endof
                2 of 200 endof
                drop 999 exit
            endcase ;
        : main 42 classify halt ;
        """
        assert compile_and_run(src) == [999], (
            "drop+push+exit pattern should let default return a value, "
            "bypassing ENDCASE's drop"
        )

    def test_first_matching_arm_wins(self):
        src = """
        : classify
            case
                1 of 100 endof
                1 of 999 endof
                drop -1 exit
            endcase ;
        : main 1 classify halt ;
        """
        assert compile_and_run(src) == [100], (
            "the first matching of-arm should run; subsequent arms must not"
        )

    def test_case_value_is_consumed_after_match(self):
        src = """
        : classify
            case
                1 of 100 endof
                drop -1 exit
            endcase ;
        : main 1 classify halt ;
        """
        assert compile_and_run(src) == [100], (
            "after a successful match the case value should be off the stack"
        )


class TestCaseFallThroughSemantics:
    """Document and verify ANS-standard fall-through behaviour."""

    def test_no_default_drops_case_value(self):
        src = """
        : classify
            case
                1 of 100 endof
                2 of 200 endof
            endcase ;
        : main 42 classify 7 halt ;
        """
        assert compile_and_run(src) == [7], (
            "case with no default and no match should leave the stack as it "
            "was before classify ran (ENDCASE's drop consumes case-val)"
        )

    def test_side_effect_only_default(self):
        """Canonical idiom: default body has side effects, doesn't push."""
        src = """
        variable seen
        : f
            case
                1 of  10 seen ! endof
                2 of  20 seen ! endof
                99 seen !
            endcase ;
        : main 42 f seen @ halt ;
        """
        assert compile_and_run(src) == [99], (
            "side-effect default should run when no arm matches; "
            "ENDCASE then drops the case-val"
        )

    def test_default_pushed_value_gets_dropped_by_endcase(self):
        """Documents the standard behaviour: a default that pushes a value
        without consuming the case-selector ends up with that pushed value
        dropped by ENDCASE, leaving the case-selector instead. This is why
        Forth idiom is to either avoid pushing in default, or use exit."""
        src = """
        : f
            case
                1 of 100 endof
                999
            endcase ;
        : main 42 f halt ;
        """
        assert compile_and_run(src) == [42], (
            "default that just pushes 999: ENDCASE drops the 999, "
            "leaving the case-selector — this is standard ANS behaviour"
        )


class TestCaseEmpty:

    def test_empty_case_just_drops(self):
        src = """
        : f case endcase ;
        : main 42 f 7 halt ;
        """
        assert compile_and_run(src) == [7], (
            "an empty case with no ofs should just drop the case value"
        )

    def test_case_with_only_default(self):
        src = """
        variable seen
        : f case 999 seen ! endcase ;
        : main 42 f seen @ halt ;
        """
        assert compile_and_run(src) == [999], (
            "case with only a side-effect default should always run it"
        )


class TestCaseWithSideEffects:
    """Each arm runs full Forth code, not just literal pushes."""

    def test_arm_can_call_other_words(self):
        src = """
        : double dup + ;
        : triple 3 * ;
        : f
            case
                1 of 10 double endof
                2 of 10 triple endof
                drop 0 exit
            endcase ;
        : main 1 f halt ;
        """
        assert compile_and_run(src) == [20], (
            "arms can contain arbitrary code, including word calls"
        )

    def test_arm_can_use_arithmetic(self):
        src = """
        : f
            case
                1 of 5 5 + endof
                2 of 100 1 - endof
                drop 0 exit
            endcase ;
        : main 2 f halt ;
        """
        assert compile_and_run(src) == [99], (
            "arms can run arithmetic primitives"
        )


class TestNestedCase:

    @pytest.mark.parametrize("outer,inner,expected", [
        (1, 10, 110),
        (1, 20, 120),
        (2, 10, 210),
        (2, 20, 220),
    ])
    def test_nested_case_inside_of_arm_matched_paths(self, outer, inner, expected):
        src = f"""
        : classify
            swap
            case
                1 of
                    case
                        10 of 110 endof
                        20 of 120 endof
                        drop 100 exit
                    endcase
                endof
                2 of
                    case
                        10 of 210 endof
                        20 of 220 endof
                        drop 200 exit
                    endcase
                endof
                drop drop 999 exit
            endcase ;
        : main {outer} {inner} classify halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"({outer},{inner}) should dispatch to {expected}"
        )

    def test_nested_case_outer_default(self):
        src = """
        : classify
            swap
            case
                1 of
                    case
                        10 of 110 endof
                        drop 100 exit
                    endcase
                endof
                drop drop 999 exit
            endcase ;
        : main 3 0 classify halt ;
        """
        assert compile_and_run(src) == [999], (
            "outer default should run when no outer arm matches"
        )


class TestStructuralErrors:

    def test_of_outside_case_raises(self):
        src = ": bad 1 of 100 endof ; : main bad halt ;"
        with pytest.raises(CompileError, match="OF without matching CASE"):
            compile_and_run(src)

    def test_endof_outside_case_raises(self):
        src = ": bad endof ; : main bad halt ;"
        with pytest.raises(CompileError):
            compile_and_run(src)

    def test_endcase_without_case_raises(self):
        src = ": bad endcase ; : main bad halt ;"
        with pytest.raises(CompileError):
            compile_and_run(src)

    def test_case_without_endcase_raises(self):
        src = ": bad case 1 of 100 endof ; : main bad halt ;"
        with pytest.raises(CompileError):
            compile_and_run(src)

    def test_case_in_interpret_state_raises(self):
        src = "case endcase : main halt ;"
        with pytest.raises(CompileError, match="CASE only works inside"):
            compile_and_run(src)


class TestSeveralArms:
    """Stress-test with more arms than the corgi example uses."""

    @pytest.mark.parametrize("n,expected", [
        (0, 1000),
        (1, 1001),
        (2, 1002),
        (3, 1003),
        (4, 1004),
        (5, 1005),
        (6, 1006),
        (7, 1007),
    ])
    def test_eight_arm_dispatch(self, n, expected):
        src = f"""
        : f
            case
                0 of 1000 endof
                1 of 1001 endof
                2 of 1002 endof
                3 of 1003 endof
                4 of 1004 endof
                5 of 1005 endof
                6 of 1006 endof
                7 of 1007 endof
                drop 9999 exit
            endcase ;
        : main {n} f halt ;
        """
        assert compile_and_run(src) == [expected], (
            f"eight-arm case should dispatch correctly for input {n}"
        )

    def test_eight_arm_default_via_exit(self):
        src = """
        : f
            case
                0 of 1000 endof
                1 of 1001 endof
                drop 9999 exit
            endcase ;
        : main 42 f halt ;
        """
        assert compile_and_run(src) == [9999], (
            "exit-based default should fire when no arm matches"
        )
