"""
Phase 5d: canonical surface words for struct field access.

Adds the four ergonomic words `>@`, `>!`, `>c@`, `>c!` to stdlib. They are
plain colons with stack effect ( base off -- val ) (or matching store form),
so they work identically to their longhand `+ @` etc. when fusion is off.

When fusion is on, the recognizer ALSO matches the 3-token form
`record .field >@` (with sugar) in addition to the 4-token canonical
`record .field + @` form, producing the same NativeFetch/NativeStore.

The store name `+!` is unavailable in zt because it's already Forth's
`(x addr -- )` increment-store. We use postfix `>!` instead — symmetric
with `>@` and unambiguous.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, compile_and_run
from zt.compile.ir import NativeFetch, NativeStore


def _compile(src: str, fuse: bool = True) -> Compiler:
    c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=fuse)
    c.include_stdlib()
    c.compile_source(src)
    return c


def _run(src: str) -> list[int]:
    from zt.sim import Z80, _read_data_stack
    c = Compiler(origin=0x8000)
    c.include_stdlib()
    c.compile_source(src)
    c.compile_main_call()
    image = c.build()
    m = Z80(); m.load(c.origin, image); m.pc = c.words["_start"].address; m.run()
    if not m.halted:
        raise TimeoutError("did not halt")
    return _read_data_stack(m, c.data_stack_top, False)


def _body_of(c: Compiler, name: str):
    return c.words[name].body


class TestSurfaceWordsExistAsColons:
    """Without any fusion involved, the four surface words must be defined
    as ordinary colons so they're available to any program."""

    @pytest.mark.parametrize("name", [">@", ">!", ">c@", ">c!"])
    def test_word_is_defined(self, name):
        c = _compile("", fuse=False)
        assert name in c.words, (
            f"{name!r} should be defined in stdlib so non-fused programs can use it"
        )

    def test_at_plus_does_offset_fetch(self):
        result = _run(
            "variable v  : main 99 v ! v 0 >@ halt ;"
        )
        assert result == [99], ">@ with offset 0 should fetch v's stored cell"

    def test_at_plus_with_nonzero_offset(self):
        result = _run(
            "create cells  10 , 20 , 30 ,  : main cells 4 >@ halt ;"
        )
        assert result == [30], "cells + 4 @ should fetch the 3rd cell (= 30)"

    def test_store_plus_writes_at_offset(self):
        result = _run(
            "create cells  0 , 0 , 0 ,  "
            ": main 77 cells 2 >!  cells 2 >@ halt ;"
        )
        assert result == [77], ">! then >@ at the same offset should round-trip"

    def test_c_at_plus_zero_extends(self):
        result = _run(
            "variable buf  : main 255 buf c! buf 0 >c@ halt ;"
        )
        assert result == [255], ">c@ should read a byte zero-extended to a cell"

    def test_c_store_plus_writes_low_byte_only(self):
        result = _run(
            "variable buf  : main 0 buf !  205 buf 0 >c!  buf 0 >c@ halt ;"
        )
        assert result == [205], ">c! stores low byte; >c@ reads it back"


class TestSurfaceWordsWorkWithFusionOff:
    """When fuse=False, source like `record .field >@` must still produce
    correct results — falling through to the threaded colon call."""

    def test_static_instance_fetch_works_without_fusion(self):
        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=False)
        c.include_stdlib()
        c.compile_source(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main 42 o .x >!  o .x >@ halt ;"
        )
        c.compile_main_call()
        image = c.build()

        from zt.sim import Z80, _read_data_stack
        m = Z80(); m.load(c.origin, image); m.pc = c.words['_start'].address; m.run()
        assert m.halted, "fuse=False program with surface words must halt"
        stack = _read_data_stack(m, c.data_stack_top, False)
        assert stack == [42], (
            f"fuse=False should still produce correct round-trip via the colon "
            f"definition of >@ / >!, got {stack!r}"
        )

    def test_static_instance_fetch_emits_colon_call_to_inlined_word_when_unfused(self):
        c = _compile(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main o .x >@ halt ;",
            fuse=False,
        )
        body = _body_of(c, "main")
        from zt.compile.ir import ColonRef
        assert ColonRef(">@") in body, (
            "with fuse=False, the call site emits ColonRef(>@); the >@ word's "
            "body itself contains the native bytes for `+ @` (because of `::`), "
            "so the unfused fallback path runs as inline native code without "
            "the per-cell NEXT-dispatch overhead of a regular `:` colon."
        )
        assert not any(isinstance(cell, (NativeFetch, NativeStore)) for cell in body), (
            "no Native* cell should appear with fuse=False"
        )

    def test_force_inline_marks_sugar_word_as_inlined(self):
        """Verify the `::` directive fired correctly and the sugar word is
        marked inlined — its body lives as native bytes at its own address,
        not as a threaded chain of cell dispatches."""
        c = _compile("", fuse=False)
        for name in (">@", ">!", ">c@", ">c!"):
            assert c.words[name].force_inline, (
                f"{name!r} must be defined with `::` so the unfused fallback "
                f"is optimal threaded code, not a colon call"
            )
            assert c.words[name].inlined, (
                f"{name!r} must have been actually inlined at definition time"
            )


class TestRecognizerFiresOnStaticSugarPattern:
    """The 3-token form `record .field >@` should fuse to the same Native*
    cell as the 4-token canonical form `record .field + @`."""

    def test_at_plus_static_sugar_fuses(self):
        c = _compile(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main o .x >@ halt ;"
        )
        body = _body_of(c, "main")
        fetches = [cell for cell in body if isinstance(cell, NativeFetch)]
        assert len(fetches) == 1, "`record .x >@` must fuse to one NativeFetch"
        assert fetches[0].width == "cell", ">@ uses cell width"
        assert fetches[0].target == "o", "target is the record name"
        assert fetches[0].address == c.words["o"].data_address + 0

    def test_store_plus_static_sugar_fuses(self):
        c = _compile(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main 99 o .x >! halt ;"
        )
        body = _body_of(c, "main")
        stores = [cell for cell in body if isinstance(cell, NativeStore)]
        assert len(stores) == 1, "`record .x >!` must fuse to one NativeStore"
        assert stores[0].width == "cell"

    def test_c_at_plus_sugar_fuses_as_byte_fetch(self):
        c = _compile(
            "0 1 -- .hp  STRUCT /a  /a record g  "
            ": main g .hp >c@ halt ;"
        )
        body = _body_of(c, "main")
        fetches = [cell for cell in body if isinstance(cell, NativeFetch)]
        assert len(fetches) == 1
        assert fetches[0].width == "byte", ">c@ uses byte width"

    def test_c_store_plus_sugar_fuses_as_byte_store(self):
        c = _compile(
            "0 1 -- .hp  STRUCT /a  /a record g  "
            ": main 7 g .hp >c! halt ;"
        )
        body = _body_of(c, "main")
        stores = [cell for cell in body if isinstance(cell, NativeStore)]
        assert len(stores) == 1
        assert stores[0].width == "byte"

    def test_canonical_and_sugar_produce_same_fused_address(self):
        c1 = _compile(
            "0 2 -- .x  STRUCT /p  /p record o  : main o .x + @ halt ;"
        )
        c2 = _compile(
            "0 2 -- .x  STRUCT /p  /p record o  : main o .x >@ halt ;"
        )
        f1 = [c for c in _body_of(c1, "main") if isinstance(c, NativeFetch)][0]
        f2 = [c for c in _body_of(c2, "main") if isinstance(c, NativeFetch)][0]
        assert f1.address == f2.address, (
            "canonical `+ @` and sugar `>@` must fuse to identical addresses"
        )
        assert f1.width == f2.width
        assert f1.target == f2.target
        assert f1.offset == f2.offset, (
            "canonical and sugar must produce the same offset field for relocation"
        )


class TestSugarRuntimeEquivalence:
    """Sugar fusion must produce identical runtime results to canonical fusion
    AND to the unfused threaded form."""

    @pytest.mark.parametrize("source_template", [
        "0 2 -- .x  STRUCT /p  /p record o  : main 42 o .x {STORE}  o .x {FETCH} halt ;",
    ])
    @pytest.mark.parametrize("store,fetch", [
        ("+ !", "+ @"),         # canonical
        (">!",  ">@"),          # sugar
    ], ids=["canonical_+_op", "sugar_op+"])
    def test_round_trip_identical(self, source_template, store, fetch):
        src = source_template.replace("{STORE}", store).replace("{FETCH}", fetch)
        result = _run(src)
        assert result == [42], (
            f"both canonical and sugar must produce 42 for the same round-trip"
        )

    def test_byte_field_round_trip_via_sugar(self):
        result = _run(
            "0 1 -- .hp  1 -- .mp  STRUCT /a  /a record g  "
            ": main 13 g .hp >c!  17 g .mp >c!  "
            "       g .hp >c@ g .mp >c@ + halt ;"
        )
        assert result == [30], (
            "byte-field sugar should round-trip distinct values per field "
            "(13 + 17 = 30)"
        )


class TestSugarTreeShakeIntegration:

    def test_sugar_fused_record_survives_tree_shake(self):
        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=True)
        c.compile_source(
            "0 2 -- .x  STRUCT /p  /p record kitchen  "
            ": main 42 kitchen .x >!  kitchen .x >@ halt ;"
        )
        c.compile_main_call()
        c.build_tree_shaken()
        assert "kitchen" in c.words, (
            "kitchen referenced only via sugar-fused cells must still survive "
            "tree-shake (target name on the cell keeps it alive)"
        )

    def test_sugar_fused_program_runs_after_tree_shake(self):
        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=True)
        c.compile_source(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main 42 o .x >! o .x >@ halt ;"
        )
        c.compile_main_call()
        image, start_addr = c.build_tree_shaken()
        from zt.sim import Z80, _read_data_stack
        m = Z80(); m.load(c.origin, image); m.pc = start_addr; m.run()
        assert m.halted, "tree-shaken sugar-fused program must halt"
        assert _read_data_stack(m, c.data_stack_top, False) == [42], (
            "tree-shake + sugar fusion + relocation must still produce the right value"
        )
