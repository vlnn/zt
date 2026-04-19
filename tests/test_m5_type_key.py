"""
Milestone-5 tests for `TYPE`, `U/MOD`, `KEY`, `KEY?`, the underlying opcodes, and `EMIT`/`TYPE` interop.
"""
from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.sim import ForthMachine, Z80, decode_screen_cell


@pytest.fixture
def fm():
    return ForthMachine()


class TestNewAsmOpcodes:

    @pytest.mark.parametrize("method,expected", [
        ("or_h",   [0xB4]),
        ("rl_c",   [0xCB, 0x11]),
        ("ld_b_l", [0x45]),
        ("ld_d_b", [0x50]),
        ("ld_e_c", [0x59]),
    ])
    def test_byte_sequence(self, method, expected):
        a = Asm(0x8000)
        getattr(a, method)()
        assert bytes(a.code) == bytes(expected), (
            f"{method}() should emit {expected}"
        )


class TestTypePrimitive:

    def _write_string(self, fm: ForthMachine, addr: int, text: bytes) -> None:
        fm.run([])
        fm._last_m.mem[addr:addr + len(text)] = text

    def test_type_single_char(self, fm):
        addr = 0xE000
        result = fm.run([
            ("label", "_setup"),
            fm.label("LIT"), 65, fm.label("LIT"), addr, fm.label("C_STORE"),
            fm.label("LIT"), addr, fm.label("LIT"), 1, fm.label("TYPE"),
        ])
        assert result.chars_out == b"A", "TYPE of 1-byte 'A' should emit 'A'"

    def test_type_full_string(self, fm):
        addr = 0xE000
        chars_code = []
        for i, ch in enumerate(b"HELLO"):
            chars_code.extend([
                fm.label("LIT"), ch,
                fm.label("LIT"), addr + i,
                fm.label("C_STORE"),
            ])
        chars_code.extend([
            fm.label("LIT"), addr,
            fm.label("LIT"), 5,
            fm.label("TYPE"),
        ])
        result = fm.run(chars_code)
        assert result.chars_out == b"HELLO", (
            "TYPE over a 5-byte buffer should emit 'HELLO'"
        )

    def test_type_empty_string(self, fm):
        result = fm.run([
            fm.label("LIT"), 0xE000,
            fm.label("LIT"), 0,
            fm.label("TYPE"),
        ])
        assert result.chars_out == b"", (
            "TYPE of 0-length string should emit nothing"
        )
        assert result.data_stack == [], (
            "TYPE with u=0 should consume both args"
        )

    def test_type_leaves_stack_empty(self, fm):
        result = fm.run([
            fm.label("LIT"), 65, fm.label("LIT"), 0xE000, fm.label("C_STORE"),
            fm.label("LIT"), 0xE000, fm.label("LIT"), 1, fm.label("TYPE"),
        ])
        assert result.data_stack == [], "TYPE should consume (addr u)"

    def test_type_advances_cursor(self, fm):
        code = []
        for i, ch in enumerate(b"AB"):
            code.extend([fm.label("LIT"), ch, fm.label("LIT"), 0xE000 + i, fm.label("C_STORE")])
        code.extend([fm.label("LIT"), 0xE000, fm.label("LIT"), 2, fm.label("TYPE")])
        fm.run(code)
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[col_addr] == 2, (
            "TYPE of 2-char string should leave cursor at col 2"
        )

    def test_type_handles_cr_in_buffer(self, fm):
        buf = b"AB\rCD"
        code = []
        for i, ch in enumerate(buf):
            code.extend([fm.label("LIT"), ch, fm.label("LIT"), 0xE000 + i, fm.label("C_STORE")])
        code.extend([fm.label("LIT"), 0xE000, fm.label("LIT"), 5, fm.label("TYPE")])
        result = fm.run(code)
        assert result.chars_out == b"AB\rCD", (
            "TYPE should pass CR through to the char core so text wraps"
        )


class TestUModPrimitive:

    @pytest.mark.parametrize("dividend,divisor,q,r", [
        (10, 3, 3, 1),
        (100, 10, 10, 0),
        (7, 2, 3, 1),
        (0, 5, 0, 0),
        (1, 1, 1, 0),
        (65535, 256, 255, 255),
        (1000, 7, 142, 6),
        (42, 6, 7, 0),
        (256, 16, 16, 0),
    ])
    def test_unsigned_division(self, fm, dividend, divisor, q, r):
        result = fm.run([
            fm.label("LIT"), dividend,
            fm.label("LIT"), divisor,
            fm.label("U_MOD_DIV"),
        ])
        assert result.data_stack == [r, q], (
            f"{dividend} u/mod {divisor} should give (r={r}, q={q}), got {result.data_stack}"
        )

    def test_stack_effect_order(self, fm):
        result = fm.run([
            fm.label("LIT"), 17,
            fm.label("LIT"), 5,
            fm.label("U_MOD_DIV"),
        ])
        assert len(result.data_stack) == 2, "U_MOD_DIV should leave 2 items"
        assert result.data_stack[-1] == 3, "top of stack should be quotient 3"
        assert result.data_stack[0] == 2, "below top should be remainder 2"


class TestKeyPrimitive:

    def test_key_no_keys_pressed_returns_zero(self, fm):
        result = fm.run([fm.label("KEY")])
        assert result.data_stack == [0], (
            "KEY with no keys pressed should return 0"
        )

    @pytest.mark.parametrize("ch", [
        "Z", "X", "C", "V",
        "A", "S", "D", "F", "G",
        "Q", "W", "E", "R", "T",
        "1", "2", "3", "4", "5",
        "0", "9", "8", "7", "6",
        "P", "O", "I", "U", "Y",
        "L", "K", "J", "H",
        "M", "N", "B",
        " ", "\r",
    ])
    def test_key_decodes_each_spectrum_key(self, fm, ch):
        result = fm.run([fm.label("KEY")], pressed_keys={ord(ch)})
        assert result.data_stack == [ord(ch)], (
            f"KEY with {ch!r} held should return its ASCII code"
        )

    def test_key_via_input_buffer_shim(self, fm):
        result = fm.run([fm.label("KEY")], input_buffer=b"A")
        assert result.data_stack == [65], (
            "KEY via input_buffer shim should read the held char"
        )


class TestKeyQueryPrimitive:

    def test_key_query_no_keys_pressed_is_false(self, fm):
        result = fm.run([fm.label("KEY_QUERY")])
        assert result.data_stack == [0], (
            "KEY? with no keys pressed should push 0"
        )

    def test_key_query_any_key_pressed_is_true(self, fm):
        result = fm.run([fm.label("KEY_QUERY")], pressed_keys={ord("A")})
        assert result.data_stack == [0xFFFF], (
            "KEY? with any key held should push -1"
        )

    def test_key_query_via_input_buffer_shim(self, fm):
        result = fm.run([fm.label("KEY_QUERY")], input_buffer=b"A")
        assert result.data_stack == [0xFFFF], (
            "KEY? via input_buffer shim should report input available"
        )


class TestKeyStatePrimitive:

    def test_key_state_unpressed_is_false(self, fm):
        result = fm.run(
            [fm.label("LIT"), ord("A"), fm.label("KEY_STATE")],
        )
        assert result.data_stack == [0], (
            "KEY-STATE for an unpressed key should return 0"
        )

    def test_key_state_pressed_is_true(self, fm):
        result = fm.run(
            [fm.label("LIT"), ord("A"), fm.label("KEY_STATE")],
            pressed_keys={ord("A")},
        )
        assert result.data_stack == [0xFFFF], (
            "KEY-STATE for a held key should return -1"
        )

    def test_key_state_detects_simultaneous_presses(self, fm):
        result = fm.run(
            [
                fm.label("LIT"), ord("A"), fm.label("KEY_STATE"),
                fm.label("LIT"), ord("S"), fm.label("KEY_STATE"),
                fm.label("LIT"), ord("D"), fm.label("KEY_STATE"),
            ],
            pressed_keys={ord("A"), ord("D")},
        )
        assert result.data_stack == [0xFFFF, 0, 0xFFFF], (
            "KEY-STATE should report A and D as held and S as not held, "
            "proving multiple simultaneous keypresses are detectable"
        )

    def test_key_state_for_unknown_ascii_is_false(self, fm):
        result = fm.run(
            [fm.label("LIT"), ord("!"), fm.label("KEY_STATE")],
            pressed_keys={ord("A")},
        )
        assert result.data_stack == [0], (
            "KEY-STATE for a character not on the Spectrum keyboard should "
            "return 0 even when other keys are held"
        )


class TestEmitRefactorInvariants:

    def test_emit_single_char_unchanged(self, fm):
        result = fm.run([fm.label("LIT"), 65, fm.label("EMIT")])
        assert result.chars_out == b"A", "EMIT(65) should still emit 'A'"
        assert result.data_stack == [], "EMIT should still consume its arg"

    def test_emit_cr_unchanged(self, fm):
        fm.run([fm.label("LIT"), 13, fm.label("EMIT")])
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 1, "CR should advance row"
        assert fm._last_m.mem[col_addr] == 0, "CR should reset col"

    def test_emit_wrap_unchanged(self, fm):
        cells = []
        for _ in range(33):
            cells.extend([fm.label("LIT"), 65, fm.label("EMIT")])
        fm.run(cells)
        row_addr = fm._prim_asm.labels["_emit_cursor_row"]
        col_addr = fm._prim_asm.labels["_emit_cursor_col"]
        assert fm._last_m.mem[row_addr] == 1, "after 33 EMITs row should be 1"
        assert fm._last_m.mem[col_addr] == 1, "after 33 EMITs col should be 1"

    def test_emit_char_core_is_exposed(self, fm):
        assert "_emit_char_core" in fm._prim_asm.labels, (
            "_emit_char_core subroutine should be labelled for TYPE to reuse"
        )


class TestTypeThenEmitInteroperability:

    def test_type_then_emit_cursor_consistent(self, fm):
        addr = 0xE000
        code = []
        for i, ch in enumerate(b"ABC"):
            code.extend([fm.label("LIT"), ch, fm.label("LIT"), addr + i, fm.label("C_STORE")])
        code.extend([
            fm.label("LIT"), addr, fm.label("LIT"), 3, fm.label("TYPE"),
            fm.label("LIT"), 68, fm.label("EMIT"),
        ])
        result = fm.run(code)
        assert result.chars_out == b"ABCD", (
            "TYPE 'ABC' then EMIT 'D' should produce 'ABCD' with continuous cursor"
        )
