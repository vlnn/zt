from __future__ import annotations

import pytest

from zt.asm import Asm
from zt.compiler import Compiler, compile_and_run
from zt.peephole import (
    DEFAULT_RULES,
    PeepholeRule,
    find_match,
    max_pattern_length,
    rules_by_specificity,
)
from zt.primitives import create_dup_fetch, create_one, create_zero


# ---------------------------------------------------------------------------
# peephole module — pure logic
# ---------------------------------------------------------------------------


class TestFindMatch:

    @pytest.mark.parametrize("elements,expected_replacement", [
        ([0, None],              "zero"),
        ([1, None],              "one"),
        ([1, "+"],               "1+"),
        ([1, "-"],               "1-"),
        ([2, "*"],               "2*"),
        (["dup", "@"],           "dup@"),
        (["swap", "drop"],       "nip"),
        (["drop", "drop"],       "2drop"),
        (["over", "over"],       "2dup"),
    ])
    def test_known_pattern_matches_expected_rule(self, elements, expected_replacement):
        rule = find_match(elements, DEFAULT_RULES)
        assert rule is not None, f"elements {elements!r} should match a default rule"
        assert rule.replacement == expected_replacement, \
            f"elements {elements!r} should map to {expected_replacement!r}"

    @pytest.mark.parametrize("elements", [
        [3, "+"],
        [None, "+"],
        ["dup", None],
        [],
        ["unknown-word"],
    ])
    def test_non_matching_elements_return_none(self, elements):
        assert find_match(elements, DEFAULT_RULES) is None, \
            f"elements {elements!r} should not match any default rule"

    def test_longest_pattern_wins(self):
        rule = find_match([1, "+"], DEFAULT_RULES)
        assert rule is not None, "[1, +] should match at least the 1+ rule"
        assert rule.replacement == "1+", \
            "[1, +] must prefer the length-2 rule over the length-1 [1] rule"

    def test_none_in_window_blocks_match(self):
        rules = (PeepholeRule((1, 2), "fused"),)
        assert find_match([1, None], rules) is None, \
            "a None inside the pattern window must prevent matching"


class TestRulesBySpecificity:

    def test_longer_patterns_come_first(self):
        ordered = rules_by_specificity(DEFAULT_RULES)
        lengths = [len(r.pattern) for r in ordered]
        assert lengths == sorted(lengths, reverse=True), \
            "rules_by_specificity should sort longest pattern first"


class TestMaxPatternLength:

    def test_returns_longest(self):
        assert max_pattern_length(DEFAULT_RULES) == 2, \
            "longest default pattern is length 2"

    def test_empty_rules_returns_zero(self):
        assert max_pattern_length(()) == 0, \
            "no rules should produce span 0"


# ---------------------------------------------------------------------------
# new fused primitives — byte-sequence tests
# ---------------------------------------------------------------------------


def _asm_with_next() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _compile_primitive(creator) -> bytes:
    a = _asm_with_next()
    creator(a)
    return a.resolve()


class TestFusedPrimitiveBytes:

    def test_zero_pushes_hl_then_loads_zero(self):
        out = _compile_primitive(create_zero)
        assert out[:4] == bytes([0xE5, 0x21, 0x00, 0x00]), \
            "ZERO should be PUSH HL; LD HL,0000"
        assert out[4] == 0xC3, \
            "ZERO should dispatch via JP NEXT"

    def test_one_pushes_hl_then_loads_one(self):
        out = _compile_primitive(create_one)
        assert out[:4] == bytes([0xE5, 0x21, 0x01, 0x00]), \
            "ONE should be PUSH HL; LD HL,0001"
        assert out[4] == 0xC3, \
            "ONE should dispatch via JP NEXT"

    def test_dup_fetch_pushes_then_reads_cell(self):
        out = _compile_primitive(create_dup_fetch)
        assert out[0] == 0xE5, "dup@ should begin with PUSH HL (dup)"
        assert out[1] == 0x5E, "dup@ should read low byte via LD E,(HL)"
        assert out[2] == 0x23, "dup@ should INC HL between byte reads"
        assert out[3] == 0x56, "dup@ should read high byte via LD D,(HL)"
        assert out[4] == 0xEB, "dup@ should EX DE,HL to move value into TOS"
        assert out[5] == 0xC3, "dup@ should dispatch via JP NEXT"

    @pytest.mark.parametrize("creator,primary,alias", [
        (create_zero,      "ZERO",       "zero"),
        (create_one,       "ONE",        "one"),
        (create_dup_fetch, "DUP_FETCH",  "dup@"),
    ])
    def test_alias_points_to_primary_label(self, creator, primary, alias):
        a = _asm_with_next()
        creator(a)
        assert a.labels[alias] == a.labels[primary], \
            f"alias '{alias}' should resolve to the same address as '{primary}'"


# ---------------------------------------------------------------------------
# compiler integration — body inspection
# ---------------------------------------------------------------------------


@pytest.fixture
def make_compiler():
    def _make(optimize: bool = True) -> Compiler:
        return Compiler(optimize=optimize)
    return _make


def _body(compiler: Compiler, name: str):
    return compiler.words[name].body


def _prim(name: str):
    from zt.ir import PrimRef
    return PrimRef(name)


def _lit_in(body) -> bool:
    from zt.ir import Literal
    return any(isinstance(c, Literal) for c in body)


class TestFusionApplies:

    @pytest.mark.parametrize("src,fused,originals", [
        (": f 0 ;",           "zero",    []),
        (": f 1 ;",           "one",     []),
        (": f 1 + ;",         "1+",      ["+"]),
        (": f 1 - ;",         "1-",      ["-"]),
        (": f 2 * ;",         "2*",      ["*"]),
        (": f dup @ ;",       "dup@",    ["dup", "@"]),
        (": f swap drop ;",   "nip",     ["swap", "drop"]),
        (": f drop drop ;",   "2drop",   ["drop"]),
        (": f over over ;",   "2dup",    ["over"]),
    ])
    def test_pattern_fuses_to_single_primitive(
        self, make_compiler, src, fused, originals,
    ):
        c = make_compiler(optimize=True)
        c.compile_source(src)
        body = _body(c, "f")
        assert _prim(fused) in body, \
            f"peephole should fuse into {fused!r}"
        assert not _lit_in(body), \
            f"fused pattern should leave no Literal cells in body of {src!r}"
        for name in originals:
            assert _prim(name) not in body, \
                f"{name!r} should not appear in body after fusion into {fused!r}"

    def test_longest_match_wins_at_compile_time(self, make_compiler):
        c = make_compiler(optimize=True)
        c.compile_source(": f 1 + ;")
        body = _body(c, "f")
        assert _prim("1+") in body, \
            "`1 +` should prefer the 1+ rule over the shorter ONE rule"
        assert _prim("one") not in body, \
            "shorter [1] rule must not fire when [1, +] matches"

    def test_literal_1_alone_still_fuses_to_one(self, make_compiler):
        c = make_compiler(optimize=True)
        c.compile_source(": f 1 ;")
        body = _body(c, "f")
        assert _prim("one") in body, \
            "literal 1 with no following + should fuse to ONE"


class TestNoOptimizeSkipsFusion:

    @pytest.mark.parametrize("src,originals,fused", [
        (": f 1 + ;",     ["+"],           "1+"),
        (": f dup @ ;",   ["dup", "@"],    "dup@"),
    ])
    def test_optimize_off_preserves_originals(
        self, make_compiler, src, originals, fused,
    ):
        c = make_compiler(optimize=False)
        c.compile_source(src)
        body = _body(c, "f")
        for name in originals:
            assert _prim(name) in body, \
                f"with optimize=False, {name!r} should remain in body"
        assert _prim(fused) not in body, \
            f"with optimize=False, fused {fused!r} must not replace originals"

    def test_optimize_off_leaves_literal_cell(self, make_compiler):
        c = make_compiler(optimize=False)
        c.compile_source(": f 0 ;")
        body = _body(c, "f")
        assert _lit_in(body), \
            "with optimize=False, literal 0 should remain as a Literal cell"
        assert _prim("zero") not in body, \
            "with optimize=False, the ZERO fusion must not fire"


class TestDoesNotOverMatch:

    def test_tick_dup_does_not_fuse_with_trailing_fetch(self, make_compiler):
        c = make_compiler(optimize=True)
        c.compile_source(": f ['] dup @ ;")
        body = _body(c, "f")
        assert _prim("dup@") not in body, \
            "['] dup compiles to a Literal(addr); a following @ must not fuse into dup@"
        assert _prim("@") in body, \
            "@ must survive when preceded by a Literal cell rather than DUP"

    def test_non_matching_literal_left_alone(self, make_compiler):
        c = make_compiler(optimize=True)
        c.compile_source(": f 3 + ;")
        body = _body(c, "f")
        assert _prim("1+") not in body, \
            "`3 +` must not fuse because literal does not match pattern value 1"
        assert _prim("+") in body, \
            "+ must remain when literal does not match"


class TestBoundaries:

    def test_pattern_does_not_cross_semicolon(self, make_compiler):
        c = make_compiler(optimize=True)
        c.compile_source(": a 1 ; : b + ;")
        assert _prim("1+") not in _body(c, "a"), \
            "literal 1 in word `a` must not fuse with + from word `b`"
        assert _prim("one") in _body(c, "a"), \
            "literal 1 in word `a` should fuse to ONE via the short rule"

    def test_pattern_does_not_eat_immediate_word(self, make_compiler):
        from zt.ir import Branch
        c = make_compiler(optimize=True)
        c.compile_source(": f 0 if drop then ;")
        body = _body(c, "f")
        assert any(isinstance(cell, Branch) and cell.kind == "0branch" for cell in body), \
            "IF must still compile a 0branch; peephole must not consume the `if` token"
        assert _prim("zero") in body, \
            "the literal 0 before IF should still fuse to ZERO"


# ---------------------------------------------------------------------------
# end-to-end — semantics preserved through simulator
# ---------------------------------------------------------------------------


class TestSemanticsPreservedEndToEnd:

    @pytest.mark.parametrize("src,expected", [
        (": main 0 halt ;",                       [0]),
        (": main 1 halt ;",                       [1]),
        (": main 5 1 + halt ;",                   [6]),
        (": main 10 1 - halt ;",                  [9]),
        (": main 7 2 * halt ;",                   [14]),
        (": main 5 6 swap drop halt ;",           [6]),
        (": main 1 2 drop drop halt ;",           []),
        (": main 1 2 over over halt ;",           [1, 2, 1, 2]),
        ("variable v : main 9 v ! v dup @ swap drop halt ;", [9]),
    ])
    def test_optimized_matches_unoptimized(self, src, expected):
        opt = compile_and_run(src, optimize=True)
        noopt = compile_and_run(src, optimize=False)
        assert opt == noopt, \
            f"optimized and unoptimized stacks must match for {src!r}"
        assert opt == expected, \
            f"run of {src!r} should produce {expected}"
