"""
Phase 5a: native fused struct-access foundation.

This patch adds the substrate for the fusion pass that lands in 5b. It does
NOT yet include the recognizer — the new IR cells and primitives exist but
no source-level pattern produces them. Tests here construct the cells
programmatically.

Four new primitives:
    (@abs)   ( -- value )    fetch cell from absolute addr in inline operand
    (!abs)   ( value -- )    store cell to absolute addr in inline operand
    (c@abs)  ( -- byte )     fetch byte from absolute addr (zero-extended)
    (c!abs)  ( value -- )    store low byte of value to absolute addr

Two new IR cells:
    NativeFetch(address, width, target)
    NativeStore(address, width, target)

`target` carries the name of the data-bearing word the address points into,
so liveness keeps it alive and tree-shake can relocate the address when the
target moves.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitives import (
    PRIMITIVES,
    create_fetch_abs,
    create_store_abs,
    create_c_fetch_abs,
    create_c_store_abs,
)
from zt.compile.compiler import Compiler, compile_and_run
from zt.compile.ir import (
    NativeFetch,
    NativeStore,
    PrimRef,
    cell_size,
    cells_from_json,
    cells_to_json,
    resolve,
)


def _asm() -> Asm:
    a = Asm(0x8000, inline_next=False)
    a.label("NEXT")
    return a


def _bytes_for(creator) -> bytes:
    a = _asm()
    creator(a)
    return a.resolve()


class TestNativeFetchPrimitiveBytes:

    def test_fetch_abs_starts_with_push_hl(self):
        out = _bytes_for(create_fetch_abs)
        assert out[0] == 0xE5, "(@abs) must preserve current TOS by pushing HL first"

    def test_fetch_abs_reads_operand_via_ix(self):
        out = _bytes_for(create_fetch_abs)
        assert out[1:7] == bytes([0xDD, 0x5E, 0x00, 0xDD, 0x56, 0x01]), (
            "(@abs) should read the absolute address from inline operand via "
            "LD E,(IX+0); LD D,(IX+1)"
        )

    def test_fetch_abs_advances_ix_past_operand(self):
        out = _bytes_for(create_fetch_abs)
        assert out[7:11] == bytes([0xDD, 0x23, 0xDD, 0x23]), (
            "(@abs) should advance IX past its 2-byte operand"
        )


class TestNativeStorePrimitiveBytes:

    def test_store_abs_reads_operand_via_ix(self):
        out = _bytes_for(create_store_abs)
        assert bytes([0xDD, 0x5E, 0x00]) in out, (
            "(!abs) should read the absolute address from inline operand via IX"
        )

    def test_store_abs_includes_pop_hl(self):
        out = _bytes_for(create_store_abs)
        assert 0xE1 in out, (
            "(!abs) must POP HL at the end to restore TOS to the next stack value"
        )


class TestNativeCByteFetchPrimitiveBytes:

    def test_c_fetch_abs_starts_with_push_hl(self):
        out = _bytes_for(create_c_fetch_abs)
        assert out[0] == 0xE5, "(c@abs) must preserve current TOS"

    def test_c_fetch_abs_zero_extends(self):
        out = _bytes_for(create_c_fetch_abs)
        assert bytes([0x26, 0x00]) in out, (
            "(c@abs) should zero-extend by setting H to 0 (LD H, 0)"
        )


class TestNativeCByteStorePrimitiveBytes:

    def test_c_store_abs_pops_hl_at_end(self):
        out = _bytes_for(create_c_store_abs)
        assert 0xE1 in out, "(c!abs) must POP HL to restore TOS"


class TestPrimitivesRegistered:

    @pytest.mark.parametrize("name", ["(@abs)", "(!abs)", "(c@abs)", "(c!abs)"])
    def test_primitive_appears_in_compiler_dictionary(self, name):
        c = Compiler(origin=0x8000)
        assert name in c.words, (
            f"{name!r} must be registered as a primitive on Compiler init"
        )

    @pytest.mark.parametrize("creator", [
        create_fetch_abs, create_store_abs,
        create_c_fetch_abs, create_c_store_abs,
    ])
    def test_creator_in_primitives_tuple(self, creator):
        assert creator in PRIMITIVES, (
            f"{creator.__name__} must be in PRIMITIVES so it gets emitted into the image"
        )


class TestNativeFetchIRCell:

    def test_native_fetch_constructs(self):
        cell = NativeFetch(address=0x9000, width="cell", target="kitchen")
        assert cell.address == 0x9000, "address field stores construction value"
        assert cell.width == "cell", "width is preserved"
        assert cell.target == "kitchen", "target is preserved"

    def test_native_fetch_is_frozen(self):
        cell = NativeFetch(address=0x9000, width="cell", target="kitchen")
        with pytest.raises((AttributeError, Exception)):
            cell.address = 0xDEAD

    def test_native_fetch_equality(self):
        a = NativeFetch(address=0x9000, width="cell", target="x")
        b = NativeFetch(address=0x9000, width="cell", target="x")
        assert a == b, "two NativeFetch with identical fields must compare equal"

    def test_native_fetch_inequality_on_address(self):
        a = NativeFetch(address=0x9000, width="cell", target="x")
        b = NativeFetch(address=0x9001, width="cell", target="x")
        assert a != b, "differing address means different cells"

    @pytest.mark.parametrize("width", ["cell", "byte"])
    def test_cell_size_is_four(self, width):
        cell = NativeFetch(address=0x9000, width=width, target="x")
        assert cell_size(cell) == 4, (
            f"NativeFetch (width={width!r}) lowers to 4 bytes "
            "(2-byte primitive ref + 2-byte address operand)"
        )


class TestNativeStoreIRCell:

    @pytest.mark.parametrize("width", ["cell", "byte"])
    def test_cell_size_is_four(self, width):
        cell = NativeStore(address=0x9000, width=width, target="x")
        assert cell_size(cell) == 4, (
            f"NativeStore (width={width!r}) lowers to 4 bytes"
        )


class TestNativeCellLowering:

    def test_native_fetch_cell_lowers_to_prim_addr_plus_target_addr(self):
        word_addrs = {"(@abs)": 0x8500}
        cell = NativeFetch(address=0x9000, width="cell", target="kitchen")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x00, 0x85, 0x00, 0x90]), (
            "NativeFetch(cell) lowers to (@abs)_addr LE + address LE"
        )

    def test_native_fetch_byte_uses_c_at_abs_primitive(self):
        word_addrs = {"(c@abs)": 0x8520}
        cell = NativeFetch(address=0x9004, width="byte", target="goblin")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x20, 0x85, 0x04, 0x90]), (
            "NativeFetch(byte) lowers via the (c@abs) primitive"
        )

    def test_native_store_cell_uses_store_abs_primitive(self):
        word_addrs = {"(!abs)": 0x8530}
        cell = NativeStore(address=0x9000, width="cell", target="x")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x30, 0x85, 0x00, 0x90]), (
            "NativeStore(cell) lowers to (!abs)_addr LE + address LE"
        )

    def test_native_store_byte_uses_c_store_abs_primitive(self):
        word_addrs = {"(c!abs)": 0x8540}
        cell = NativeStore(address=0x9000, width="byte", target="x")
        out = resolve([cell], word_addrs)
        assert out == bytes([0x40, 0x85, 0x00, 0x90]), (
            "NativeStore(byte) lowers via (c!abs)"
        )


class TestNativeCellJSONRoundTrip:

    @pytest.mark.parametrize("cell", [
        NativeFetch(address=0x9000, width="cell", target="kitchen"),
        NativeFetch(address=0x9004, width="byte", target="goblin"),
        NativeStore(address=0x9000, width="cell", target="x"),
        NativeStore(address=0x9000, width="byte", target="hp"),
    ], ids=["fetch_cell", "fetch_byte", "store_cell", "store_byte"])
    def test_roundtrip_preserves_cell(self, cell):
        round_tripped = cells_from_json(cells_to_json([cell]))
        assert round_tripped == [cell], (
            f"JSON roundtrip should preserve {cell!r} bit-for-bit"
        )


class TestNativeCellLiveness:

    def test_native_fetch_marks_target_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {
            "main": [
                NativeFetch(address=0x9000, width="cell", target="kitchen"),
                PrimRef("halt"),
            ],
        }
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "kitchen" in liveness.words, (
            "NativeFetch's target name must be live so its data survives tree-shake"
        )

    def test_native_fetch_marks_fetch_abs_primitive_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {"main": [NativeFetch(0x9000, "cell", "x"), PrimRef("halt")]}
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(@abs)" in liveness.words, (
            "NativeFetch(cell) depends on the (@abs) primitive"
        )

    def test_native_fetch_byte_marks_c_fetch_abs_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {"main": [NativeFetch(0x9000, "byte", "x"), PrimRef("halt")]}
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(c@abs)" in liveness.words, (
            "NativeFetch(byte) depends on the (c@abs) primitive"
        )

    def test_native_store_marks_store_abs_live(self):
        from zt.compile.liveness import compute_liveness

        bodies = {"main": [NativeStore(0x9000, "cell", "x"), PrimRef("halt")]}
        liveness = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "(!abs)" in liveness.words, (
            "NativeStore(cell) depends on the (!abs) primitive"
        )


class TestNativeRuntimeViaInjectedCell:
    """End-to-end: hand-build an image with a `(@abs)` or `(!abs)` call in a
    threaded body, run it, observe. Validates the new primitive's bytes
    behave correctly at runtime (no fusion pass involved — that's 5b)."""

    def _build_runnable(self, body_cells, data_addr=0xC000, data_bytes=b"\x42\x00"):
        from zt.compile.compiler import Compiler
        from zt.compile.ir import resolve as ir_resolve, cell_size

        c = Compiler(origin=0x8000, inline_primitives=False, inline_next=False)
        c.compile_source(": main halt halt halt halt halt halt ;")
        c.compile_main_call()
        c.build()

        word_addrs = {n: w.address for n, w in c.words.items()}
        body_start = c.words["main"].address + 3
        new_bytes = ir_resolve(body_cells, word_addrs, base_address=body_start)
        offset = body_start - c.origin
        for i in range(len(new_bytes)):
            c.asm.code[offset + i] = new_bytes[i]
        return c, bytes(c.asm.code), data_addr, data_bytes

    def test_native_fetch_reads_at_runtime(self):
        from zt.sim import Z80, _read_data_stack

        body = [
            NativeFetch(address=0xC000, width="cell", target="v"),
            PrimRef("halt"),
        ]
        c, image, data_addr, data_bytes = self._build_runnable(
            body, data_addr=0xC000, data_bytes=b"\x42\x00"
        )
        m = Z80()
        m.load(c.origin, image)
        m.load(data_addr, data_bytes)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "execution should halt cleanly after fetch"
        stack = _read_data_stack(m, c.data_stack_top, False)
        assert stack == [0x42], (
            f"(@abs) should push the cell at 0xC000 (= 0x42), got {stack!r}"
        )

    def test_native_fetch_byte_zero_extends(self):
        from zt.sim import Z80, _read_data_stack

        body = [
            NativeFetch(address=0xC000, width="byte", target="v"),
            PrimRef("halt"),
        ]
        c, image, data_addr, data_bytes = self._build_runnable(
            body, data_addr=0xC000, data_bytes=b"\xAB\xFF\xFF"
        )
        m = Z80()
        m.load(c.origin, image)
        m.load(data_addr, data_bytes)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "execution should halt"
        stack = _read_data_stack(m, c.data_stack_top, False)
        assert stack == [0xAB], (
            f"(c@abs) should push the byte at 0xC000 zero-extended (= 0xAB), "
            f"got {stack!r}"
        )

    def test_native_store_writes_at_runtime(self):
        from zt.sim import Z80
        from zt.compile.ir import Literal

        body = [
            Literal(0xCAFE),
            NativeStore(address=0xC000, width="cell", target="v"),
            PrimRef("halt"),
        ]
        c, image, data_addr, data_bytes = self._build_runnable(
            body, data_addr=0xC000, data_bytes=b"\x00\x00\x00"
        )
        m = Z80()
        m.load(c.origin, image)
        m.load(data_addr, data_bytes)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "execution should halt"
        result = m._rw(0xC000)
        assert result == 0xCAFE, (
            f"(!abs) should write 0xCAFE to 0xC000, got {result:#06x}"
        )

    def test_native_byte_store_writes_low_byte(self):
        from zt.sim import Z80
        from zt.compile.ir import Literal

        body = [
            Literal(0x12CD),
            NativeStore(address=0xC000, width="byte", target="v"),
            PrimRef("halt"),
        ]
        c, image, data_addr, data_bytes = self._build_runnable(
            body, data_addr=0xC000, data_bytes=b"\x00\xFF\xFF"
        )
        m = Z80()
        m.load(c.origin, image)
        m.load(data_addr, data_bytes)
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "execution should halt"
        assert m._rb(0xC000) == 0xCD, (
            f"(c!abs) should write only the low byte (0xCD) to 0xC000, "
            f"got {m._rb(0xC000):#04x}"
        )
        assert m._rb(0xC001) == 0xFF, (
            "byte store must NOT touch the byte at addr+1"
        )


class TestNativeCellTreeShakeRelocation:
    """If a NativeFetch points at a record that gets relocated by tree-shake,
    the cell's address must be updated to the new data_address."""

    def test_relocate_native_fetch_updates_address(self):
        from zt.compile.tree_shake import _relocate_native_addresses

        cell = NativeFetch(address=0x9000, width="cell", target="kitchen")
        new_data_addrs = {"kitchen": 0x8500}
        relocated = _relocate_native_addresses([cell], new_data_addrs)
        assert relocated[0].address == 0x8500, (
            "tree-shake must update NativeFetch.address to the new data_address"
        )
        assert relocated[0].target == "kitchen", "target name is preserved"
        assert relocated[0].width == "cell", "width is preserved"

    def test_relocate_native_store_updates_address(self):
        from zt.compile.tree_shake import _relocate_native_addresses

        cell = NativeStore(address=0x9000, width="byte", target="goblin")
        new_data_addrs = {"goblin": 0x8600}
        relocated = _relocate_native_addresses([cell], new_data_addrs)
        assert relocated[0].address == 0x8600, "NativeStore is also relocated"

    def test_relocate_leaves_unaffected_target_alone(self):
        from zt.compile.tree_shake import _relocate_native_addresses

        cell = NativeFetch(address=0x9000, width="cell", target="kitchen")
        new_data_addrs = {"some_other_word": 0x8500}
        relocated = _relocate_native_addresses([cell], new_data_addrs)
        assert relocated[0].address == 0x9000, (
            "if target isn't in the relocation map, leave address alone"
        )

    def test_relocate_leaves_other_cells_unchanged(self):
        from zt.compile.tree_shake import _relocate_native_addresses
        from zt.compile.ir import Literal

        cells = [
            Literal(42),
            NativeFetch(address=0x9000, width="cell", target="x"),
            PrimRef("halt"),
        ]
        relocated = _relocate_native_addresses(cells, {"x": 0x8000})
        assert relocated[0] == Literal(42), "non-Native cells pass through"
        assert relocated[2] == PrimRef("halt"), "PrimRef passes through"
        assert relocated[1].address == 0x8000, "only NativeFetch is touched"
