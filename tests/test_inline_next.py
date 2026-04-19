"""
Tests for inlining the `NEXT` dispatcher into primitive tails instead of emitting `jp NEXT`, covering asm wiring, image size, and end-to-end semantics.
"""
from __future__ import annotations

import pytest

from zt.asm import Asm
from zt.compiler import Compiler, compile_and_run
from zt.primitives import (
    PRIMITIVES,
    create_2drop,
    create_2dup,
    create_2swap,
    create_and,
    create_branch,
    create_c_fetch,
    create_c_store,
    create_docol,
    create_drop,
    create_dup,
    create_equals,
    create_exit,
    create_fetch,
    create_invert,
    create_next,
    create_nip,
    create_one,
    create_one_minus,
    create_one_plus,
    create_or,
    create_over,
    create_plus,
    create_r_fetch,
    create_r_from,
    create_rot,
    create_store,
    create_swap,
    create_to_r,
    create_tuck,
    create_two_slash,
    create_two_star,
    create_xor,
    create_zero,
)


NEXT_BODY = bytes([
    0xDD, 0x5E, 0x00,
    0xDD, 0x56, 0x01,
    0xDD, 0x23,
    0xDD, 0x23,
    0xD5,
    0xC9,
])


class TestEmitNextBody:

    def test_emits_twelve_canonical_bytes(self):
        a = Asm(0x8000)
        a.emit_next_body()
        assert bytes(a.code) == NEXT_BODY, \
            "emit_next_body should produce the canonical 12-byte NEXT sequence"

    def test_matches_create_next_sans_label(self):
        labeled = Asm(0x8000)
        create_next(labeled)
        inlined = Asm(0x8000)
        inlined.emit_next_body()
        assert bytes(labeled.code) == bytes(inlined.code), \
            "emit_next_body should match create_next byte-for-byte (sans label)"

    def test_produces_no_fixups(self):
        a = Asm(0x8000)
        a.emit_next_body()
        out = a.resolve()
        assert len(out) == 12, \
            "emit_next_body should resolve without any label fixups"


class TestAsmDispatch:

    def test_default_flag_is_true(self):
        a = Asm(0x8000)
        assert a.inline_next is True, \
            "Asm.inline_next should default to True for best runtime performance"

    def test_dispatch_without_inlining_emits_jp_next(self):
        a = Asm(0x8000, inline_next=False)
        a.label("NEXT")
        a.dispatch()
        out = a.resolve()
        assert out == bytes([0xC3, 0x00, 0x80]), \
            "dispatch with inline_next=False should emit JP NEXT (3 bytes) to the NEXT label"

    def test_dispatch_with_inlining_emits_next_body(self):
        a = Asm(0x8000, inline_next=True)
        a.dispatch()
        assert bytes(a.code) == NEXT_BODY, \
            "dispatch with inline_next=True should emit the 12-byte NEXT body inline"

    def test_inlined_dispatch_needs_no_next_label(self):
        a = Asm(0x8000, inline_next=True)
        a.dispatch()
        out = a.resolve()
        assert len(out) == 12, \
            "inlined dispatch should resolve without requiring a NEXT label fixup"

    def test_two_dispatches_double_the_body(self):
        a = Asm(0x8000, inline_next=True)
        a.dispatch()
        a.dispatch()
        assert bytes(a.code) == NEXT_BODY + NEXT_BODY, \
            "two inlined dispatches should paste the NEXT body twice"


DISPATCH_TAIL_PRIMITIVES = [
    create_docol, create_exit,
    create_dup, create_drop, create_swap, create_over,
    create_rot, create_nip, create_tuck,
    create_2dup, create_2drop, create_2swap,
    create_to_r, create_r_from, create_r_fetch,
    create_plus, create_one_plus, create_one_minus,
    create_two_star, create_two_slash,
    create_zero, create_one,
    create_and, create_or, create_xor, create_invert,
    create_equals,
    create_fetch, create_store,
    create_c_fetch, create_c_store,
    create_branch,
]


@pytest.mark.parametrize("creator", DISPATCH_TAIL_PRIMITIVES,
                         ids=lambda c: c.__name__)
def test_primitive_ends_with_inlined_next_when_enabled(creator):
    a = Asm(0x8000, inline_next=True)
    a.label("NEXT")
    creator(a)
    out = a.resolve()
    assert out.endswith(NEXT_BODY), \
        f"{creator.__name__} should end with the inlined NEXT body when inline_next=True"


@pytest.mark.parametrize("creator", DISPATCH_TAIL_PRIMITIVES,
                         ids=lambda c: c.__name__)
def test_primitive_ends_with_jp_next_when_disabled(creator):
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    creator(a)
    out = a.resolve()
    assert out[-3] == 0xC3, \
        f"{creator.__name__} should end with JP (0xC3) when inline_next is disabled"
    assert out[-2:] == bytes([0x00, 0x80]), \
        f"{creator.__name__} should target NEXT at origin 0x8000 when inline_next is disabled"


class TestImageSizeGrowsWithInlining:

    def _image_len(self, *, inline_next: bool) -> int:
        a = Asm(0x8000, inline_next=inline_next)
        for creator in PRIMITIVES:
            creator(a)
        return len(a.resolve())

    def test_inlined_image_is_larger(self):
        plain = self._image_len(inline_next=False)
        inlined = self._image_len(inline_next=True)
        assert inlined > plain, \
            "inlining the NEXT body into every primitive should grow the image"

    def test_growth_is_roughly_nine_bytes_per_dispatch_site(self):
        plain = self._image_len(inline_next=False)
        inlined = self._image_len(inline_next=True)
        delta = inlined - plain
        assert 200 <= delta <= 1000, \
            f"image growth should be a few hundred bytes (9 per dispatch site), got {delta}"


class TestCompilerWiring:

    def test_compiler_defaults_to_inlined(self):
        c = Compiler()
        assert c.asm.inline_next is True, \
            "Compiler should default to inline_next=True for best runtime performance"

    def test_compiler_threads_flag_to_asm(self):
        c = Compiler(inline_next=True)
        assert c.asm.inline_next is True, \
            "Compiler(inline_next=True) should set the flag on its Asm instance"

    def test_compiler_exposes_flag_on_self(self):
        c = Compiler(inline_next=True)
        assert c.inline_next is True, \
            "Compiler should expose inline_next on itself for introspection"


class TestSemanticsPreservedEndToEnd:

    @pytest.mark.parametrize("src,expected", [
        (": main 0 halt ;",                                 [0]),
        (": main 1 halt ;",                                 [1]),
        (": main 5 1 + halt ;",                             [6]),
        (": main 10 3 - halt ;",                            [7]),
        (": main 7 2 * halt ;",                             [14]),
        (": main 1 2 3 rot halt ;",                         [2, 3, 1]),
        (": main 4 5 swap drop halt ;",                     [5]),
        (": main 1 2 over over halt ;",                     [1, 2, 1, 2]),
        (": main 1 2 drop drop halt ;",                     []),
        (": main $ff $0f and halt ;",                       [0x0f]),
        (": main $f0 $0f or halt ;",                        [0xff]),
        (": main 1 3 lshift halt ;",                        [8]),
        ("variable v : main 42 v ! v @ halt ;",             [42]),
        (": f dup + ; : main 9 f halt ;",                   [18]),
        (": inc 1+ ; : main 5 inc inc inc halt ;",          [8]),
    ])
    def test_inline_next_preserves_stack_results(self, src, expected):
        plain = compile_and_run(src, inline_next=False)
        inlined = compile_and_run(src, inline_next=True)
        assert plain == expected, \
            f"non-inlined run of {src!r} should leave {expected}, got {plain}"
        assert inlined == plain, \
            f"inlined run of {src!r} should match non-inlined result ({plain}), got {inlined}"

    @pytest.mark.parametrize("optimize", [False, True])
    def test_inline_next_composes_with_peephole(self, optimize):
        src = ": main 1 2 + dup @ drop halt ;"
        plain = compile_and_run(
            "variable v : main 42 v ! v @ halt ;",
            inline_next=False, optimize=optimize,
        )
        inlined = compile_and_run(
            "variable v : main 42 v ! v @ halt ;",
            inline_next=True, optimize=optimize,
        )
        assert inlined == plain, \
            f"inline_next should be orthogonal to peephole optimizer (optimize={optimize})"
