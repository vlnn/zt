"""
Phase 5c: dynamic-instance fusion.

Where 5b handles the case `record .field + @` (instance and offset both
known at compile time), 5c handles `.field + @` and `.field >@` patterns
that appear *inside accessor colons*, where the instance is a runtime
value living on the stack:

    : actor-x  ( actor -- x )  .x + @ ;
    : actor-y  ( actor -- y )  .y >@  ;     \\ same thing, sugar form

Both compile to one NativeOffsetFetch IR cell that lowers to:

    LD E,(IX+0)        ; read offset operand inline
    LD D,(IX+1)
    INC IX  INC IX
    ADD HL, DE         ; HL = instance + offset
    LD A,(HL)  INC HL  LD H,(HL)  LD L,A   ; deref into HL
    JP NEXT

Total 4 bytes per access, ~107 T-states (vs 8-12 bytes / ~140-200 T-states
threaded). The cells carry no `target` field — there's nothing to relocate
under tree-shake — so they're simpler than their static cousins.

The recognizer fires the dynamic patterns when the current compile-state
token itself is a compile-time-known value (number / constant / struct
size / `--`-defined field offset) AND the next 1-2 tokens are the right
shape. It runs after the static-instance check so an explicit record
prefix always wins.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler
from zt.compile.ir import (
    NativeFetch, NativeStore,
    NativeOffsetFetch, NativeOffsetStore,
    PrimRef, Literal, cell_size,
)


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


class TestNativeOffsetIRCells:

    @pytest.mark.parametrize("klass", [NativeOffsetFetch, NativeOffsetStore])
    @pytest.mark.parametrize("width", ["cell", "byte"])
    def test_construction_and_size(self, klass, width):
        cell = klass(offset=2, width=width)
        assert cell.offset == 2, "offset is preserved on construction"
        assert cell.width == width, "width is preserved"
        assert cell_size(cell) == 4, (
            f"{klass.__name__} (width={width}) lowers to 4 bytes "
            "(2-byte primitive ref + 2-byte offset operand)"
        )

    def test_inequality_on_offset(self):
        a = NativeOffsetFetch(offset=2, width="cell")
        b = NativeOffsetFetch(offset=4, width="cell")
        assert a != b, "different offsets means different cells"

    @pytest.mark.parametrize("klass", [NativeOffsetFetch, NativeOffsetStore])
    def test_rejects_negative_offset(self, klass):
        with pytest.raises(ValueError):
            klass(offset=-1, width="cell")

    @pytest.mark.parametrize("klass", [NativeOffsetFetch, NativeOffsetStore])
    def test_rejects_too_large_offset(self, klass):
        with pytest.raises(ValueError):
            klass(offset=0x10000, width="cell")


class TestNativeOffsetCellLowering:

    def test_offset_fetch_cell_lowers(self):
        from zt.compile.ir import resolve
        word_addrs = {"(@off)": 0x8500}
        cell = NativeOffsetFetch(offset=4, width="cell")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x00, 0x85, 0x04, 0x00]), (
            "NativeOffsetFetch(cell) lowers to (@off)_addr LE + offset LE"
        )

    def test_offset_fetch_byte_uses_c_at_off(self):
        from zt.compile.ir import resolve
        word_addrs = {"(c@off)": 0x8520}
        cell = NativeOffsetFetch(offset=1, width="byte")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x20, 0x85, 0x01, 0x00]), (
            "byte-width offset fetch uses (c@off)"
        )

    def test_offset_store_uses_store_off(self):
        from zt.compile.ir import resolve
        word_addrs = {"(!off)": 0x8530}
        cell = NativeOffsetStore(offset=2, width="cell")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x30, 0x85, 0x02, 0x00])

    def test_offset_byte_store_uses_c_store_off(self):
        from zt.compile.ir import resolve
        word_addrs = {"(c!off)": 0x8540}
        cell = NativeOffsetStore(offset=3, width="byte")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x40, 0x85, 0x03, 0x00])


class TestNativeOffsetCellJSONRoundTrip:

    @pytest.mark.parametrize("cell", [
        NativeOffsetFetch(offset=0, width="cell"),
        NativeOffsetFetch(offset=4, width="byte"),
        NativeOffsetStore(offset=2, width="cell"),
        NativeOffsetStore(offset=1, width="byte"),
    ], ids=["fetch_cell_0", "fetch_byte_4", "store_cell_2", "store_byte_1"])
    def test_roundtrip_preserves_cell(self, cell):
        from zt.compile.ir import cells_from_json, cells_to_json
        round_tripped = cells_from_json(cells_to_json([cell]))
        assert round_tripped == [cell], (
            f"JSON roundtrip should preserve {cell!r}"
        )


class TestDynamicRecognizerCanonical:
    """Pattern: `<offset> + <op>` inside a colon body, where offset is
    compile-time-known and there's no record prefix."""

    def test_dynamic_canonical_fetch_fuses(self):
        c = _compile(
            "0 2 -- .x  STRUCT /p  "
            ": actor-x  ( actor -- x )  .x + @ ;"
        )
        body = _body_of(c, "actor-x")
        fetches = [cell for cell in body if isinstance(cell, NativeOffsetFetch)]
        assert len(fetches) == 1, (
            f"`.x + @` (no record prefix) should fuse to NativeOffsetFetch, "
            f"got body {body!r}"
        )
        assert fetches[0].offset == 0, ".x is at offset 0"
        assert fetches[0].width == "cell"

    def test_dynamic_canonical_store_fuses(self):
        c = _compile(
            "0 2 -- .x  2 -- .y  STRUCT /p  "
            ": actor-set-y  ( y actor -- )  .y + ! ;"
        )
        body = _body_of(c, "actor-set-y")
        stores = [cell for cell in body if isinstance(cell, NativeOffsetStore)]
        assert len(stores) == 1
        assert stores[0].offset == 2, ".y is at offset 2"
        assert stores[0].width == "cell"

    def test_dynamic_canonical_byte_fetch_fuses(self):
        c = _compile(
            "0 1 -- .hp  STRUCT /a  "
            ": actor-hp  ( actor -- hp )  .hp + c@ ;"
        )
        body = _body_of(c, "actor-hp")
        fetches = [cell for cell in body if isinstance(cell, NativeOffsetFetch)]
        assert len(fetches) == 1
        assert fetches[0].width == "byte"

    def test_dynamic_canonical_byte_store_fuses(self):
        c = _compile(
            "0 1 -- .hp  STRUCT /a  "
            ": actor-set-hp  ( hp actor -- )  .hp + c! ;"
        )
        body = _body_of(c, "actor-set-hp")
        stores = [cell for cell in body if isinstance(cell, NativeOffsetStore)]
        assert len(stores) == 1
        assert stores[0].width == "byte"

    def test_dynamic_canonical_fires_on_raw_numeric_offset(self):
        c = _compile(": foo  ( base -- val )  4 + @ ;")
        body = _body_of(c, "foo")
        fetches = [cell for cell in body if isinstance(cell, NativeOffsetFetch)]
        assert len(fetches) == 1, "raw numeric offset should fuse too"
        assert fetches[0].offset == 4

    def test_dynamic_canonical_fires_on_plain_constant(self):
        c = _compile(
            "8 constant EIGHT  : foo  ( base -- val )  EIGHT + @ ;"
        )
        body = _body_of(c, "foo")
        fetches = [cell for cell in body if isinstance(cell, NativeOffsetFetch)]
        assert len(fetches) == 1
        assert fetches[0].offset == 8


class TestDynamicRecognizerSugar:
    """Pattern: `<offset> >@` (or other sugar) inside a colon body."""

    def test_dynamic_sugar_fetch_fuses(self):
        c = _compile(
            "0 2 -- .x  STRUCT /p  "
            ": actor-x  ( actor -- x )  .x >@ ;"
        )
        body = _body_of(c, "actor-x")
        fetches = [cell for cell in body if isinstance(cell, NativeOffsetFetch)]
        assert len(fetches) == 1, (
            f"`.x >@` (sugar, no record prefix) should fuse, got body {body!r}"
        )
        assert fetches[0].offset == 0

    def test_dynamic_sugar_store_fuses(self):
        c = _compile(
            "0 2 -- .y  2 -- .x  STRUCT /p  "
            ": actor-set-x  ( x actor -- )  .x >! ;"
        )
        body = _body_of(c, "actor-set-x")
        stores = [cell for cell in body if isinstance(cell, NativeOffsetStore)]
        assert len(stores) == 1
        assert stores[0].offset == 2

    @pytest.mark.parametrize("sugar,width,is_fetch", [
        (">@",  "cell", True),
        (">!",  "cell", False),
        (">c@", "byte", True),
        (">c!", "byte", False),
    ])
    def test_each_sugar_word_fuses_to_correct_cell(self, sugar, width, is_fetch):
        c = _compile(f": foo  ( base -- ? )  4 {sugar} ;")
        body = _body_of(c, "foo")
        target_class = NativeOffsetFetch if is_fetch else NativeOffsetStore
        fused = [cell for cell in body if isinstance(cell, target_class)]
        assert len(fused) == 1, f"sugar {sugar!r} should fuse to {target_class.__name__}"
        assert fused[0].width == width


class TestDynamicFusionDoesNotFireWhenItShouldnt:

    def test_no_fuse_with_runtime_offset(self):
        c = _compile(
            ": foo  ( base off -- val )  + @ ;"
        )
        body = _body_of(c, "foo")
        offset_cells = [c for c in body
                        if isinstance(c, (NativeOffsetFetch, NativeOffsetStore))]
        assert offset_cells == [], (
            "with offset coming from the stack, no compile-time value is known; "
            "fusion must NOT fire"
        )

    def test_no_fuse_with_wrong_middle_op(self):
        c = _compile(": foo  ( base -- val )  4 - @ ;")
        body = _body_of(c, "foo")
        assert not any(isinstance(c, (NativeOffsetFetch, NativeOffsetStore))
                       for c in body), "subtraction in middle slot must not fuse"

    def test_no_fuse_with_unrelated_terminal_op(self):
        c = _compile(": foo  ( base -- )  4 + drop ;")
        body = _body_of(c, "foo")
        assert not any(isinstance(c, (NativeOffsetFetch, NativeOffsetStore))
                       for c in body), "drop after + is not a fetch/store"

    def test_static_instance_takes_priority_over_dynamic(self):
        """When the current token IS a record, the static recognizer fires
        and dynamic does not — the resulting cell is NativeFetch (with target),
        not NativeOffsetFetch."""
        c = _compile(
            "0 2 -- .x  STRUCT /p  /p record kitchen  "
            ": main kitchen .x >@ halt ;"
        )
        body = _body_of(c, "main")
        static_fetches = [c for c in body if isinstance(c, NativeFetch)]
        dynamic_fetches = [c for c in body if isinstance(c, NativeOffsetFetch)]
        assert len(static_fetches) == 1, (
            "explicit record prefix should produce static NativeFetch"
        )
        assert len(dynamic_fetches) == 0, (
            "static recognizer should win — no dynamic cell emitted"
        )


class TestDynamicFusionRuntime:
    """Real end-to-end: an accessor colon called on a real instance."""

    def test_dynamic_accessor_round_trip(self):
        result = _run(
            "0 2 -- .x  2 -- .y  STRUCT /p  /p record o  "
            ": setx  ( x actor -- )  .x >! ; "
            ": getx  ( actor -- x )  .x >@ ; "
            ": main  42 o setx  o getx  halt ;"
        )
        assert result == [42], (
            f"accessor colons that fuse to NativeOffsetStore/Fetch must round-trip "
            f"the value; got {result}"
        )

    def test_dynamic_byte_accessor_round_trip(self):
        result = _run(
            "0 1 -- .hp  STRUCT /a  /a record g  "
            ": gethp  ( actor -- hp )  .hp >c@ ; "
            ": sethp  ( hp actor -- )  .hp >c! ; "
            ": main  77 g sethp  g gethp  halt ;"
        )
        assert result == [77], "byte accessor colons must round-trip"

    def test_two_dynamic_accessors_in_one_colon(self):
        result = _run(
            "0 2 -- .x  2 -- .y  STRUCT /p  /p record o  "
            ": init  ( actor -- )  10 over .x >!  20 over .y >!  drop ; "
            ": sumxy ( actor -- s )  dup .x >@  swap .y >@  + ; "
            ": main  o init  o sumxy  halt ;"
        )
        assert result == [30], "two dynamic accessors in one colon should compose"

    def test_dynamic_pattern_with_raw_numeric_offset(self):
        result = _run(
            "create cells  10 , 20 , 30 , 40 , "
            ": main  cells 2 + @  cells 4 + @  +  halt ;"
        )
        assert result == [50], (
            "raw numeric offsets in dynamic position should fuse and "
            "still compute correctly: cells[1]=20 + cells[2]=30 = 50"
        )


class TestDynamicFusionLiveness:

    def test_offset_fetch_marks_at_off_primitive_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {
            "main": [NativeOffsetFetch(offset=0, width="cell"), PrimRef("halt")],
        }
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(@off)" in liveness.words, (
            "NativeOffsetFetch(cell) depends on the (@off) primitive"
        )

    def test_offset_byte_fetch_marks_c_at_off_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {
            "main": [NativeOffsetFetch(offset=0, width="byte"), PrimRef("halt")],
        }
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(c@off)" in liveness.words

    def test_offset_store_marks_store_off_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {
            "main": [NativeOffsetStore(offset=0, width="cell"), PrimRef("halt")],
        }
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(!off)" in liveness.words


class TestDynamicFusionTreeShakeSurvivesCleanly:
    """Dynamic cells carry no target — no relocation needed. But the tree-shake
    pipeline must still rebuild correctly when these cells are present."""

    def test_program_using_dynamic_fusion_runs_after_tree_shake(self):
        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=True)
        c.include_stdlib()
        c.compile_source(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": getx  ( actor -- x )  .x >@ ; "
            ": main  42 o .x >! o getx halt ;"
        )
        c.compile_main_call()
        image, start_addr = c.build_tree_shaken()

        from zt.sim import Z80, _read_data_stack
        m = Z80(); m.load(c.origin, image); m.pc = start_addr; m.run()
        assert m.halted
        assert _read_data_stack(m, c.data_stack_top, False) == [42], (
            "tree-shaken program with both static AND dynamic fusion must run correctly"
        )

    def test_off_primitives_dropped_when_no_dynamic_fusion(self):
        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False, fuse=True)
        c.include_stdlib()
        c.compile_source(
            "0 2 -- .x  STRUCT /p  /p record o  "
            ": main  42 o .x >! o .x >@ halt ;"
        )
        c.compile_main_call()
        c.build_tree_shaken()
        assert "(@off)" not in c.words, (
            "if no dynamic fusion fires anywhere, (@off) should be tree-shaken"
        )
