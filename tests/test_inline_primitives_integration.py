"""
Integration tests for the primitive-inliner: compile-time flag, image integrity, inspection preservation, orthogonality with other flags, and semantics.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, compile_and_run


# ---------------------------------------------------------------------------
# compiler flag plumbing
# ---------------------------------------------------------------------------


class TestCompilerFlag:

    def test_default_is_enabled(self):
        c = Compiler()
        assert c.inline_primitives is True, \
            "Compiler should default to inline_primitives=True for best runtime performance"

    def test_flag_accessible_on_instance(self):
        c = Compiler(inline_primitives=True)
        assert c.inline_primitives is True, \
            "Compiler(inline_primitives=True) should expose the flag for introspection"

    def test_inline_context_built_only_when_enabled(self):
        c_off = Compiler(inline_primitives=False)
        c_on = Compiler(inline_primitives=True)
        assert c_off._inline_context is None, \
            "when disabled, no InlineContext should be built (nothing to amortise)"
        assert c_on._inline_context is not None, \
            "when enabled, the InlineContext should be ready before user code compiles"


# ---------------------------------------------------------------------------
# byte-level: colon prologue changes with the flag
# ---------------------------------------------------------------------------


def _bytes_at_word(c: Compiler, name: str, count: int) -> bytes:
    word = c.words[name]
    offset = word.address - c.origin
    return bytes(c.asm.code[offset:offset + count])


class TestBytesAtColonStart:

    def test_threaded_colon_starts_with_call_docol(self):
        c = Compiler(inline_primitives=False)
        c.compile_source(": double dup + ;")
        assert _bytes_at_word(c, "double", 1)[0] == 0xCD, \
            "without inlining, a colon body must start with CALL (0xCD)"

    def test_inlined_colon_does_not_start_with_call(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ;")
        first_byte = _bytes_at_word(c, "double", 1)[0]
        assert first_byte != 0xCD, \
            "with inlining, double must not start with CALL DOCOL"

    def test_inlined_double_starts_with_dup_opcodes(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ;")
        # dup = 0xE5 (PUSH HL); plus = 0xD1 0x19 (POP DE; ADD HL,DE)
        assert _bytes_at_word(c, "double", 3) == bytes([0xE5, 0xD1, 0x19]), \
            "inlined double should be PUSH HL; POP DE; ADD HL,DE (then dispatch)"

    def test_non_inlinable_colon_still_starts_with_call(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": f 0 if drop then ;")
        assert _bytes_at_word(c, "f", 1)[0] == 0xCD, \
            "a colon with IF/THEN is not inlinable; it must still start with CALL DOCOL"

    def test_colon_calling_another_colon_stays_threaded(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ; : quad double double ;")
        assert _bytes_at_word(c, "quad", 1)[0] == 0xCD, \
            "step 3 is shallow; calling another colon must not be inlined"

    def test_empty_colon_becomes_just_dispatch(self):
        c = Compiler(inline_primitives=True, inline_next=False)
        c.compile_source(": nothing ;")
        assert _bytes_at_word(c, "nothing", 1)[0] == 0xC3, \
            "an empty inlined colon should collapse to a single JP NEXT (0xC3)"


# ---------------------------------------------------------------------------
# introspection: Word.body preserved for zt inspect
# ---------------------------------------------------------------------------


class TestBodyPreservedForInspection:

    def test_body_still_populated_after_inlining(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ;")
        assert c.words["double"].body, \
            "Word.body must remain populated after inlining so zt inspect still works"

    def test_body_references_original_primitive_addresses(self):
        from zt.compile.ir import PrimRef
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ;")
        body = c.words["double"].body
        assert PrimRef("dup") in body, \
            "body should still reference PrimRef(dup) for introspection"
        assert PrimRef("+") in body, \
            "body should still reference PrimRef(+) for introspection"

    def test_kind_remains_colon(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ;")
        assert c.words["double"].kind == "colon", \
            "inlined colons should retain kind='colon' for redefinition-warning logic"


# ---------------------------------------------------------------------------
# build integrity: no dangling fixups, no body_cell_refs crash
# ---------------------------------------------------------------------------


class TestBuildIntegrity:

    def test_build_succeeds_after_inlining_single_colon(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": double dup + ; : main 5 double halt ;")
        c.compile_main_call()
        image = c.build()
        assert c.words["double"].inlined is True, (
            "a two-primitive colon should be inlined when inline_primitives=True"
        )
        assert image[c.words["main"].address - c.origin] == 0xCD, (
            "main should start with CALL DOCOL (0xCD) even when called words are inlined"
        )

    def test_build_succeeds_with_mixed_inlinable_and_not(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(
            ": double dup + ; "
            ": maybe 0 if drop then ; "
            ": main 5 double halt ;"
        )
        c.compile_main_call()
        c.build()
        assert c.words["double"].inlined is True, (
            "the inlinable colon 'double' should be flagged inlined"
        )
        assert c.words["maybe"].inlined is False, (
            "the colon containing IF/THEN must NOT be inlined (non-trivial control flow)"
        )

    def test_resolve_body_cells_does_not_fail(self):
        c = Compiler(inline_primitives=True)
        c.compile_source(": a dup + ; : b dup + ; : c dup + ;")
        c.compile_source(": main 1 a halt ;")
        c.compile_main_call()
        c.build()


# ---------------------------------------------------------------------------
# semantic equivalence
# ---------------------------------------------------------------------------


class TestSemanticsPreserved:

    @pytest.mark.parametrize("src,expected", [
        (": main 0 halt ;",                                 [0]),
        (": main 1 halt ;",                                 [1]),
        (": main 5 1 + halt ;",                             [6]),
        (": main 10 3 - halt ;",                            [7]),
        (": main 7 2 * halt ;",                             [14]),
        (": main 4 5 swap drop halt ;",                     [5]),
        (": main 1 2 over over halt ;",                     [1, 2, 1, 2]),
        (": main 1 2 drop drop halt ;",                     []),
        (": main $ff $0f and halt ;",                       [0x0f]),
        (": main $f0 $0f or halt ;",                        [0xff]),
        ("variable v : main 42 v ! v @ halt ;",             [42]),
        (": double dup + ; : main 9 double halt ;",         [18]),
        (": inc 1+ ; : main 5 inc inc inc halt ;",          [8]),
        (": quad dup + dup + ; : main 3 quad halt ;",       [12]),
        (": main 1 3 lshift halt ;",                        [8]),
        (": shl3 3 lshift ; : main 1 shl3 halt ;",          [8]),
        (": main 1 0 lshift halt ;",                        [1]),
        (": main 0 5 lshift halt ;",                        [0]),
        (": main 5 5 = halt ;",                             [0xFFFF]),
        (": main 5 6 = halt ;",                             [0]),
        (": eq = ; : main 7 7 eq halt ;",                   [0xFFFF]),
        (": eq = ; : main 7 8 eq halt ;",                   [0]),
    ])
    def test_inline_primitives_preserves_stack_results(self, src, expected):
        baseline = compile_and_run(src, inline_primitives=False)
        inlined = compile_and_run(src, inline_primitives=True)
        assert baseline == expected, \
            f"baseline run of {src!r} should leave {expected}, got {baseline}"
        assert inlined == baseline, \
            f"inlined run of {src!r} should match baseline ({baseline}), got {inlined}"


class TestInlinedColonCallableFromThreaded:

    def test_threaded_outer_calls_inlined_inner(self):
        result = compile_and_run(
            ": double dup + ; : quad double double ; : main 3 quad halt ;",
            inline_primitives=True,
        )
        assert result == [12], \
            "a threaded colon calling an inlined one must still produce the correct result"

    def test_literal_before_inlined_call_is_visible(self):
        result = compile_and_run(
            ": double dup + ; : main 5 double halt ;",
            inline_primitives=True,
        )
        assert result == [10], \
            "a literal pushed before an inlined colon call must still be on the stack"


class TestUserRedefinitionSafety:

    def test_redefined_primitive_keeps_user_semantics(self):
        result = compile_and_run(
            ": dup 99 ; : main dup halt ;",
            inline_primitives=True,
        )
        assert result == [99], \
            "when the user redefines dup as a colon, main must see the user's definition, not the primitive"


# ---------------------------------------------------------------------------
# orthogonality: inline_next × inline_primitives × optimize
# ---------------------------------------------------------------------------


class TestOrthogonalityMatrix:

    @pytest.mark.parametrize("inline_next", [False, True])
    @pytest.mark.parametrize("inline_primitives", [False, True])
    @pytest.mark.parametrize("optimize", [False, True])
    def test_all_flag_combinations_give_identical_stacks(
        self, inline_next, inline_primitives, optimize,
    ):
        src = ": inc 1+ ; : main 5 inc inc inc halt ;"
        result = compile_and_run(
            src,
            inline_next=inline_next,
            inline_primitives=inline_primitives,
            optimize=optimize,
        )
        combo = (inline_next, inline_primitives, optimize)
        assert result == [8], \
            f"combo (inline_next={combo[0]}, inline_primitives={combo[1]}, optimize={combo[2]}) should leave [8], got {result}"

    @pytest.mark.parametrize("inline_next", [False, True])
    @pytest.mark.parametrize("inline_primitives", [False, True])
    def test_variable_access_orthogonal_to_flags(self, inline_next, inline_primitives):
        src = "variable v : main 42 v ! v @ halt ;"
        result = compile_and_run(
            src, inline_next=inline_next, inline_primitives=inline_primitives,
        )
        assert result == [42], \
            f"variable fetch/store must work under all flag combinations; got {result}"


# ---------------------------------------------------------------------------
# image size: inlined programs should be no larger than a sensible bound
# ---------------------------------------------------------------------------


class TestImageSizeReasonable:

    def test_inlining_simple_colons_does_not_explode_image(self):
        src = ": double dup + ; : quadruple double double ; : main 3 quadruple halt ;"
        baseline = compile_and_run.__wrapped__ if hasattr(compile_and_run, "__wrapped__") else None
        from zt.compile.compiler import build_from_source
        plain_image, _ = build_from_source(src, inline_primitives=False)
        inlined_image, _ = build_from_source(src, inline_primitives=True)
        growth = len(inlined_image) - len(plain_image)
        assert abs(growth) < 200, \
            f"inlining a 3-colon program should not change image size dramatically; got {growth:+d} bytes"
