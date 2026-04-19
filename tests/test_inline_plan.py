"""
Tests for `plan_colon_inlining` / `is_colon_inlinable` / `emit_inline_plan`: which colon words qualify for inlining and the bytes the plan emits.
"""
from __future__ import annotations

import pytest

from zt.asm import Asm
from zt.compiler import Compiler
from zt.inline_bodies import (
    InlineContext,
    InlineStep,
    emit_inline_plan,
    is_colon_inlinable,
    plan_colon_inlining,
)
from zt.primitives import PRIMITIVES


_DISPATCH_TO_ZERO = bytes([0xC3, 0x00, 0x00])


@pytest.fixture(scope="module")
def context() -> InlineContext:
    return InlineContext.build(PRIMITIVES)


@pytest.fixture
def compiler() -> Compiler:
    return Compiler(optimize=False)


@pytest.fixture
def optimizing_compiler() -> Compiler:
    return Compiler(optimize=True)


# ---------------------------------------------------------------------------
# plan_colon_inlining — positive cases
# ---------------------------------------------------------------------------


class TestPlanPositiveCases:

    def test_double_plans_dup_then_plus(self, compiler, context):
        compiler.compile_source(": double dup + ;")
        plan = plan_colon_inlining(compiler.words["double"], compiler.words, context)
        assert plan == [
            InlineStep(kind="prim", key="dup"),
            InlineStep(kind="prim", key="plus"),
        ], "double should plan as [dup, plus]"

    def test_single_literal_plans_lit_step(self, compiler, context):
        compiler.compile_source(": five 5 ;")
        plan = plan_colon_inlining(compiler.words["five"], compiler.words, context)
        assert plan == [InlineStep(kind="lit", value=5)], \
            "a lone literal should plan as a single lit step"

    def test_lit_then_prim(self, compiler, context):
        compiler.compile_source(": add10 10 + ;")
        plan = plan_colon_inlining(compiler.words["add10"], compiler.words, context)
        assert plan == [
            InlineStep(kind="lit", value=10),
            InlineStep(kind="prim", key="plus"),
        ], "add10 should plan as [lit 10, plus]"

    def test_empty_colon_plans_empty_list(self, compiler, context):
        compiler.compile_source(": nothing ;")
        plan = plan_colon_inlining(compiler.words["nothing"], compiler.words, context)
        assert plan == [], "an empty colon body should plan as an empty step list"

    def test_two_lits_in_a_row(self, compiler, context):
        compiler.compile_source(": pair 3 7 ;")
        plan = plan_colon_inlining(compiler.words["pair"], compiler.words, context)
        assert plan == [
            InlineStep(kind="lit", value=3),
            InlineStep(kind="lit", value=7),
        ], "two consecutive literals should produce two lit steps"

    def test_fused_one_plus_from_peephole(self, optimizing_compiler, context):
        optimizing_compiler.compile_source(": inc 1 + ;")
        plan = plan_colon_inlining(
            optimizing_compiler.words["inc"],
            optimizing_compiler.words,
            context,
        )
        assert plan == [InlineStep(kind="prim", key="one_plus")], \
            "with peephole on, `1 +` should fuse and plan as a single one_plus step"


class TestIsColonInlinableMirrorsPlan:

    @pytest.mark.parametrize("src,word_name,expected", [
        (": a dup + ;",          "a", True),
        (": a 5 ;",              "a", True),
        (": a ;",                "a", True),
        (": a 0 if drop then ;", "a", False),
    ])
    def test_is_inlinable_matches_plan_is_not_none(
        self, compiler, context, src, word_name, expected,
    ):
        compiler.compile_source(src)
        word = compiler.words[word_name]
        assert is_colon_inlinable(word, compiler.words, context) is expected, \
            f"is_colon_inlinable({word_name!r}) should return {expected}"


# ---------------------------------------------------------------------------
# plan_colon_inlining — negative cases
# ---------------------------------------------------------------------------


class TestPlanNegativeCases:

    def test_if_then_is_rejected(self, compiler, context):
        compiler.compile_source(": f 0 if drop then ;")
        plan = plan_colon_inlining(compiler.words["f"], compiler.words, context)
        assert plan is None, "colons with IF/THEN must not be inlinable"

    def test_begin_until_is_rejected(self, compiler, context):
        compiler.compile_source(": f 3 begin 1- dup 0= until ;")
        plan = plan_colon_inlining(compiler.words["f"], compiler.words, context)
        assert plan is None, "colons with BEGIN/UNTIL must not be inlinable"

    def test_do_loop_is_rejected(self, compiler, context):
        compiler.compile_source(": f 10 0 do i loop ;")
        plan = plan_colon_inlining(compiler.words["f"], compiler.words, context)
        assert plan is None, "colons with DO/LOOP must not be inlinable"

    def test_calling_another_colon_is_rejected(self, compiler, context):
        compiler.compile_source(": double dup + ; : quad double double ;")
        plan = plan_colon_inlining(compiler.words["quad"], compiler.words, context)
        assert plan is None, \
            "calling another colon must not be inlined (step 3 is shallow)"

    def test_non_inlinable_primitive_rejected(self, compiler, context):
        compiler.compile_source(": f 3 4 < ;")
        plan = plan_colon_inlining(compiler.words["f"], compiler.words, context)
        assert plan is None, \
            "a colon containing a non-whitelisted primitive (< uses jp_p) must not be inlinable"

    def test_user_redefined_primitive_not_inlined(self, compiler, context):
        compiler.compile_source(": dup 5 ; : f dup ;")
        plan = plan_colon_inlining(compiler.words["f"], compiler.words, context)
        assert plan is None, \
            "when dup is redefined as a user colon, f calling 'dup' must not inline as the primitive"

    def test_primitive_word_is_not_inlinable_as_colon(self, compiler, context):
        plan = plan_colon_inlining(compiler.words["dup"], compiler.words, context)
        assert plan is None, \
            "a primitive word (kind='prim') must not be plannable as a colon"


# ---------------------------------------------------------------------------
# emit_inline_plan — byte-level
# ---------------------------------------------------------------------------


def _asm_with_next_at_zero() -> Asm:
    a = Asm(0x0000, inline_next=False)
    a.label("NEXT")
    return a


class TestEmitInlinePlan:

    def test_empty_plan_emits_only_dispatch(self, context):
        asm = _asm_with_next_at_zero()
        emit_inline_plan(asm, [], context)
        assert asm.resolve() == _DISPATCH_TO_ZERO, \
            "an empty plan must emit a single dispatch (3 bytes)"

    def test_prim_step_emits_registry_bytes_plus_dispatch(self, context):
        asm = _asm_with_next_at_zero()
        emit_inline_plan(asm, [InlineStep(kind="prim", key="dup")], context)
        expected = context.registry["dup"] + _DISPATCH_TO_ZERO
        assert asm.resolve() == expected, \
            "a single prim step must emit the registry bytes followed by dispatch"

    def test_lit_step_emits_push_hl_ld_hl_then_dispatch(self, context):
        asm = _asm_with_next_at_zero()
        emit_inline_plan(asm, [InlineStep(kind="lit", value=0x1234)], context)
        # push hl (E5); ld hl, 0x1234 (21 34 12); jp 0 (C3 00 00)
        expected = bytes([0xE5, 0x21, 0x34, 0x12]) + _DISPATCH_TO_ZERO
        assert asm.resolve() == expected, \
            "a lit step must emit PUSH HL; LD HL,nn followed by dispatch"

    def test_lit_masks_value_to_16_bits(self, context):
        asm = _asm_with_next_at_zero()
        emit_inline_plan(asm, [InlineStep(kind="lit", value=-1)], context)
        # -1 as 16-bit unsigned is 0xFFFF
        expected = bytes([0xE5, 0x21, 0xFF, 0xFF]) + _DISPATCH_TO_ZERO
        assert asm.resolve() == expected, \
            "a lit step with negative value must emit the 16-bit two's-complement form"

    def test_multi_step_plan_emits_in_order(self, context):
        asm = _asm_with_next_at_zero()
        plan = [
            InlineStep(kind="lit", value=42),
            InlineStep(kind="prim", key="one_plus"),
        ]
        emit_inline_plan(asm, plan, context)
        expected = (
            bytes([0xE5, 0x21, 0x2A, 0x00])
            + context.registry["one_plus"]
            + _DISPATCH_TO_ZERO
        )
        assert asm.resolve() == expected, \
            "multi-step plans must emit each step in order then dispatch once at the end"

    def test_emit_appends_to_existing_code(self, context):
        asm = _asm_with_next_at_zero()
        asm.nop()
        emit_inline_plan(asm, [InlineStep(kind="prim", key="drop")], context)
        expected = bytes([0x00]) + context.registry["drop"] + _DISPATCH_TO_ZERO
        assert asm.resolve() == expected, \
            "emit should append to existing asm code, not replace it"


# ---------------------------------------------------------------------------
# roundtrip: plan + emit
# ---------------------------------------------------------------------------


class TestPlanEmitRoundtrip:

    @pytest.mark.parametrize("src,word_name", [
        (": double dup + ;",   "double"),
        (": add10 10 + ;",     "add10"),
        (": five 5 ;",         "five"),
        (": empty ;",          "empty"),
        (": pair 3 7 ;",       "pair"),
    ])
    def test_plan_then_emit_produces_executable_bytes(
        self, compiler, context, src, word_name,
    ):
        compiler.compile_source(src)
        plan = plan_colon_inlining(
            compiler.words[word_name], compiler.words, context,
        )
        assert plan is not None, \
            f"{word_name} should be inlinable for roundtrip test"
        asm = _asm_with_next_at_zero()
        emit_inline_plan(asm, plan, context)
        out = asm.resolve()
        assert out.endswith(_DISPATCH_TO_ZERO), \
            f"emitted bytes for {word_name} must end with a dispatch"
        assert len(out) >= 3, \
            f"emitted bytes for {word_name} must contain at least a dispatch"
