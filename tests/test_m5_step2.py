"""
Milestone-5 step-2 tests covering the newly-added asm opcodes, sim opcodes, and `EMIT` / cursor behaviour.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.sim import FLAG_C, FLAG_H, FLAG_N, FLAG_Z, ForthMachine, Z80, decode_screen_cell


@pytest.fixture
def fm():
    return ForthMachine()


def _run_raw(code: bytes, *, origin: int = 0x8000, max_ticks: int = 1000) -> Z80:
    m = Z80()
    m.load(origin, code)
    m.pc = origin
    m.sp = 0xFF00
    m.run(max_ticks)
    return m


class TestNewAsmOpcodes:

    @pytest.mark.parametrize("method,arg,expected", [
        ("cp_n",       13,      [0xFE, 0x0D]),
        ("cp_n",       32,      [0xFE, 0x20]),
        ("and_n",      0x18,    [0xE6, 0x18]),
        ("and_n",      0xFF,    [0xE6, 0xFF]),
        ("or_n",       0x40,    [0xF6, 0x40]),
        ("or_n",       0x01,    [0xF6, 0x01]),
    ])
    def test_immediate_byte_sequence(self, method, arg, expected):
        a = Asm(0x8000)
        getattr(a, method)(arg)
        assert bytes(a.code) == bytes(expected), (
            f"{method}({arg:#04x}) should emit {expected}"
        )

    @pytest.mark.parametrize("method,expected", [
        ("or_b",        [0xB0]),
        ("rrca",        [0x0F]),
        ("ld_b_a",      [0x47]),
        ("ld_a_ind_de", [0x1A]),
        ("inc_h",       [0x24]),
    ])
    def test_single_byte_opcode(self, method, expected):
        a = Asm(0x8000)
        getattr(a, method)()
        assert bytes(a.code) == bytes(expected), (
            f"{method}() should emit {expected}"
        )

    @pytest.mark.parametrize("method,opcode", [
        ("ld_a_ind_nn", 0x3A),
        ("ld_ind_nn_a", 0x32),
    ])
    def test_absolute_addr_literal(self, method, opcode):
        a = Asm(0x8000)
        getattr(a, method)(0x5AFF)
        assert bytes(a.code) == bytes([opcode, 0xFF, 0x5A]), (
            f"{method}(0x5AFF) should emit {opcode:#04x} with little-endian address"
        )

    @pytest.mark.parametrize("method,opcode", [
        ("ld_a_ind_nn", 0x3A),
        ("ld_ind_nn_a", 0x32),
    ])
    def test_absolute_addr_label(self, method, opcode):
        a = Asm(0x8000)
        a.nop()
        a.label("target")
        getattr(a, method)("target")
        out = a.resolve()
        assert out[0] == 0x00, "NOP should be first byte"
        assert out[1] == opcode, f"{method} should emit opcode {opcode:#04x}"
        assert out[2:4] == bytes([0x01, 0x80]), (
            f"{method}('target') should resolve label to 0x8001"
        )


class TestNewSimOpcodes:

    def test_ld_a_ind_nn_reads_memory(self):
        m = Z80()
        m.load(0x9000, bytes([0x42]))
        m.load(0x8000, bytes([0x3A, 0x00, 0x90, 0x76]))
        m.pc = 0x8000
        m.run(100)
        assert m.a == 0x42, "LD A,($9000) should read byte at that address into A"

    def test_ld_ind_nn_a_writes_memory(self):
        m = _run_raw(bytes([0x3E, 0x99, 0x32, 0x00, 0x90, 0x76]))
        assert m.mem[0x9000] == 0x99, "LD ($9000),A should write A to that address"

    def test_ld_a_ind_de_reads_via_de(self):
        m = Z80()
        m.load(0x9000, bytes([0xAB]))
        m.load(0x8000, bytes([0x11, 0x00, 0x90, 0x1A, 0x76]))
        m.pc = 0x8000
        m.sp = 0xFF00
        m.run(100)
        assert m.a == 0xAB, "LD A,(DE) should read the byte at the DE address"

    @pytest.mark.parametrize("initial,expected", [
        (0x00, 0x01), (0x0F, 0x10), (0x7F, 0x80), (0xFF, 0x00),
    ])
    def test_inc_h_increments_register(self, initial, expected):
        m = _run_raw(bytes([0x26, initial, 0x24, 0x76]))
        assert m.h == expected, f"INC H on {initial:#04x} should produce {expected:#04x}"

    @pytest.mark.parametrize("a_value,n,expected_a,expected_z", [
        (0xFF, 0x0F, 0x0F, False),
        (0xFF, 0x00, 0x00, True),
        (0x18, 0x18, 0x18, False),
        (0x23, 0x18, 0x00, True),
    ])
    def test_and_n(self, a_value, n, expected_a, expected_z):
        m = _run_raw(bytes([0x3E, a_value, 0xE6, n, 0x76]))
        assert m.a == expected_a, f"{a_value:#04x} AND {n:#04x} should be {expected_a:#04x}"
        assert bool(m.f & FLAG_Z) is expected_z, (
            f"AND result {m.a:#04x} Z flag should be {expected_z}"
        )
        assert m.f & FLAG_H, "AND n should always set H flag"

    @pytest.mark.parametrize("a_value,n,expected", [
        (0x18, 0x40, 0x58),
        (0x00, 0x00, 0x00),
        (0x55, 0xAA, 0xFF),
    ])
    def test_or_n(self, a_value, n, expected):
        m = _run_raw(bytes([0x3E, a_value, 0xF6, n, 0x76]))
        assert m.a == expected, f"{a_value:#04x} OR {n:#04x} should be {expected:#04x}"
        assert not (m.f & FLAG_H), "OR n should clear H flag"

    @pytest.mark.parametrize("a_value,n,expected_z,expected_c", [
        (13, 13, True, False),
        (13, 14, False, True),
        (14, 13, False, False),
        (32, 32, True, False),
    ])
    def test_cp_n(self, a_value, n, expected_z, expected_c):
        m = _run_raw(bytes([0x3E, a_value, 0xFE, n, 0x76]))
        assert m.a == a_value, "CP n should leave A unchanged"
        assert bool(m.f & FLAG_Z) is expected_z, (
            f"CP {a_value}, {n} should {'set' if expected_z else 'clear'} Z"
        )
        assert bool(m.f & FLAG_C) is expected_c, (
            f"CP {a_value}, {n} should {'set' if expected_c else 'clear'} C"
        )
        assert m.f & FLAG_N, "CP should set N flag"

    @pytest.mark.parametrize("initial,expected_a,expected_c", [
        (0b00000001, 0b10000000, True),
        (0b10000000, 0b01000000, False),
        (0b11111111, 0b11111111, True),
        (0b00000000, 0b00000000, False),
        (0b10000001, 0b11000000, True),
    ])
    def test_rrca(self, initial, expected_a, expected_c):
        m = _run_raw(bytes([0x3E, initial, 0x0F, 0x76]))
        assert m.a == expected_a, (
            f"RRCA of {initial:#010b} should give {expected_a:#010b}"
        )
        assert bool(m.f & FLAG_C) is expected_c, (
            f"RRCA should set C from old bit 0 ({initial & 1})"
        )
        assert not (m.f & FLAG_H), "RRCA should clear H flag"
        assert not (m.f & FLAG_N), "RRCA should clear N flag"


class TestEmitSingleChar:

    @pytest.mark.parametrize("char,expected", [
        (65, b"A"),
        (32, b" "),
        (33, b"!"),
        (127, b"\x7f"),
    ])
    def test_single_emit(self, fm, char, expected):
        result = fm.run([fm.label("LIT"), char, fm.label("EMIT")])
        assert result.chars_out == expected, (
            f"emitting {char} should yield chars_out = {expected!r}"
        )
        assert result.data_stack == [], "EMIT should consume its argument"

    def test_emit_leaves_screen_cell_with_identity_bytes(self, fm):
        fm.run([fm.label("LIT"), 65, fm.label("EMIT")])
        assert decode_screen_cell(fm._last_m.mem, 0, 0) == 65, (
            "EMIT of 65 should write 8 copies of 65 to cell (0, 0)"
        )

    def test_emit_advances_cursor_column(self, fm):
        fm.run([fm.label("LIT"), 65, fm.label("EMIT")])
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 0, "one EMIT should leave cursor on row 0"
        assert fm._last_m.mem[col_addr] == 1, "one EMIT should leave cursor at col 1"


class TestEmitMultipleChars:

    def test_two_chars(self, fm):
        result = fm.run([
            fm.label("LIT"), 72, fm.label("EMIT"),
            fm.label("LIT"), 73, fm.label("EMIT"),
        ])
        assert result.chars_out == b"HI", "two EMITs should produce a 2-char string"

    def test_fill_row(self, fm):
        cells = []
        for ch in range(65, 65 + 32):
            cells.extend([fm.label("LIT"), ch, fm.label("EMIT")])
        result = fm.run(cells)
        expected = bytes(range(65, 65 + 32))
        assert result.chars_out.replace(b"\r", b"") == expected, (
            "32 distinct EMITs should fill row 0 with their byte values"
        )

    def test_cursor_wraps_to_next_row_after_col_32(self, fm):
        cells = []
        for _ in range(33):
            cells.extend([fm.label("LIT"), 65, fm.label("EMIT")])
        fm.run(cells)
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 1, (
            "after 33 EMITs, cursor should have wrapped to row 1"
        )
        assert fm._last_m.mem[col_addr] == 1, (
            "after 33 EMITs, cursor col should be 1 on row 1"
        )


class TestEmitCarriageReturn:

    def test_cr_alone_yields_carriage_return_byte(self, fm):
        result = fm.run([fm.label("LIT"), 13, fm.label("EMIT")])
        assert result.chars_out == b"\r", (
            "emitting CR on an empty screen should yield b'\\r'"
        )

    def test_cr_moves_cursor_to_next_row_col_zero(self, fm):
        fm.run([fm.label("LIT"), 13, fm.label("EMIT")])
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 1, "CR should advance row by 1"
        assert fm._last_m.mem[col_addr] == 0, "CR should reset col to 0"

    def test_cr_does_not_write_to_screen(self, fm):
        fm.run([fm.label("LIT"), 13, fm.label("EMIT")])
        assert decode_screen_cell(fm._last_m.mem, 0, 0) == 0, (
            "CR should not write a glyph at (0, 0)"
        )

    def test_text_then_cr_then_text(self, fm):
        lits = [
            (65, "EMIT"), (66, "EMIT"), (67, "EMIT"),
            (13, "EMIT"),
            (68, "EMIT"), (69, "EMIT"), (70, "EMIT"),
        ]
        cells = []
        for val, word in lits:
            cells.extend([fm.label("LIT"), val, fm.label(word)])
        result = fm.run(cells)
        assert result.chars_out == b"ABC\rDEF", (
            "text, CR, text should produce 'ABC\\rDEF'"
        )


class TestCursorResetsPerExecute:

    def test_two_runs_do_not_share_cursor_state(self, fm):
        fm.run([fm.label("LIT"), 65, fm.label("EMIT")])
        result2 = fm.run([fm.label("LIT"), 66, fm.label("EMIT")])
        assert result2.chars_out == b"B", (
            "second fm.run should start with a fresh (0, 0) cursor"
        )


class TestEmitInColonDefinition:

    def test_emit_inside_colon(self, fm):
        result = fm.run_colon(
            body_cells=[fm.label("LIT"), 88, fm.label("EMIT"), "EXIT"],
            main_cells=["DOUBLE"],
        )
        assert result.chars_out == b"X", "EMIT called from a colon word should still print"
