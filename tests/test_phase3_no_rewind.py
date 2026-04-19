"""
Regression tests ensuring the Phase-3 inliner never shrinks or rewinds `asm.code` and that inlined and threaded colons produce identical runtime results.
"""
import pytest

from zt.asm import Asm
from zt.compiler import Compiler, compile_and_run
from zt.ir import Literal, PrimRef


def _compile(source: str, **flags) -> Compiler:
    c = Compiler(**flags)
    c.compile_source(source)
    return c


class TestAsmCodeNeverShrinks:

    class ShrinkWatchdog(bytearray):
        def __delitem__(self, index):
            raise AssertionError(
                f"asm.code should never have items deleted during Phase 3; "
                f"got __delitem__({index!r})"
            )

        def pop(self, *args, **kwargs):
            raise AssertionError(
                "asm.code should never have pop() called during Phase 3"
            )

        def __setitem__(self, index, value):
            if isinstance(index, slice):
                raise AssertionError(
                    f"asm.code should never have slice assignment during Phase 3; "
                    f"got __setitem__({index!r})"
                )
            super().__setitem__(index, value)

    def test_building_plain_colon_does_not_shrink_asm_code(self):
        c = Compiler(inline_primitives=False, inline_next=False)
        c.asm.code = self.ShrinkWatchdog(c.asm.code)
        c.compile_source(": double dup + ; : main 5 double halt ;")
        c.compile_main_call()
        c.build()

    def test_building_inlined_colon_does_not_shrink_asm_code(self):
        c = Compiler(inline_primitives=True, inline_next=False)
        c.asm.code = self.ShrinkWatchdog(c.asm.code)
        c.compile_source(": double dup + ; : main 5 double halt ;")
        c.compile_main_call()
        c.build()

    def test_building_control_flow_does_not_shrink_asm_code(self):
        c = Compiler(inline_primitives=False, inline_next=False)
        c.asm.code = self.ShrinkWatchdog(c.asm.code)
        c.compile_source(": f dup if drop then ; : main 5 f halt ;")
        c.compile_main_call()
        c.build()


class TestColonInlined:

    def test_simple_inlinable_colon_has_inlined_flag(self):
        c = _compile(": double dup + ; : main 5 double halt ;",
                     inline_primitives=True)
        assert c.words["double"].inlined is True, (
            ": double dup + ; should be flagged inlined under inline_primitives=True"
        )

    def test_inlined_colon_preserves_body_cells(self):
        c = _compile(": double dup + ; : main 5 double halt ;",
                     inline_primitives=True)
        body = c.words["double"].body
        assert PrimRef("dup") in body and PrimRef("+") in body, (
            "inlined colon must still carry its IR body cells for introspection"
        )

    def test_inlined_colon_produces_correct_stack(self):
        assert compile_and_run(": double dup + ; : main 5 double halt ;",
                               inline_primitives=True) == [10], (
            "inlined `double` of 5 should yield 10 on the stack"
        )


class TestColonNotInlined:

    def test_colon_containing_control_flow_is_not_inlined(self):
        c = _compile(": f dup if drop then ; : main 5 f halt ;",
                     inline_primitives=True)
        assert c.words["f"].inlined is False, (
            "colon with IF/THEN should NOT be inlined (contains non-whitelisted branches)"
        )

    def test_non_inlined_colon_emits_docol_prologue(self):
        c = _compile(": f dup if drop then ; : main 5 f halt ;",
                     inline_primitives=True)
        c.compile_main_call()
        image = c.build()
        offset = c.words["f"].address - c.origin
        assert image[offset] == 0xCD, (
            "non-inlined colon should begin with CALL DOCOL (0xCD)"
        )

    def test_non_inlined_colon_semantics(self):
        assert compile_and_run(": f dup 0= if 42 swap drop then ; : main 0 f halt ;",
                               inline_primitives=True) == [42], (
            "non-inlined `f` of 0 should replace TOS with 42"
        )


class TestInlineVsThreadedProduceSameResult:

    @pytest.mark.parametrize("src, expected", [
        (": double dup + ; : main 5 double halt ;", [10]),
        (": inc 1+ ; : main 9 inc inc inc halt ;", [12]),
        (": five 5 ; : main five five + halt ;", [10]),
    ])
    def test_inlined_equals_threaded(self, src, expected):
        threaded = compile_and_run(src, inline_primitives=False)
        inlined = compile_and_run(src, inline_primitives=True)
        assert threaded == expected, (
            f"threaded run of {src!r} should produce {expected}"
        )
        assert inlined == threaded, (
            f"inlined run must match threaded result for {src!r}"
        )
