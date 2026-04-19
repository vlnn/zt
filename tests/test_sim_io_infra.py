"""
Tests for the simulator's IO infrastructure: `screen_addr`, `decode_screen_cell`, `TEST_FONT`, the preloaded font, and `ForthResult.chars_out`.
"""
from __future__ import annotations

import pytest

from zt.sim import (
    SPECTRUM_FONT_BASE,
    SPECTRUM_SCREEN_BASE,
    TEST_FONT,
    ForthMachine,
    ForthResult,
    decode_screen_cell,
    screen_addr,
)


@pytest.fixture
def fm():
    return ForthMachine()


class TestScreenAddr:

    @pytest.mark.parametrize("row,col,line,expected", [
        (0, 0, 0, 0x4000),
        (0, 0, 7, 0x4700),
        (0, 31, 0, 0x401F),
        (1, 0, 0, 0x4020),
        (7, 0, 0, 0x40E0),
        (7, 31, 7, 0x47FF),
        (8, 0, 0, 0x4800),
        (15, 31, 7, 0x4FFF),
        (16, 0, 0, 0x5000),
        (23, 0, 0, 0x50E0),
        (23, 31, 0, 0x50FF),
        (23, 31, 7, 0x57FF),
    ])
    def test_addr(self, row, col, line, expected):
        assert screen_addr(row, col, line) == expected, (
            f"screen_addr({row}, {col}, line={line}) should be {expected:#06x}"
        )

    def test_line_defaults_to_zero(self):
        assert screen_addr(5, 7) == screen_addr(5, 7, 0), (
            "screen_addr should default line to 0"
        )

    @pytest.mark.parametrize("row", range(24))
    def test_every_row_lands_in_pixel_area(self, row):
        addr = screen_addr(row, 0, 0)
        assert SPECTRUM_SCREEN_BASE <= addr < SPECTRUM_SCREEN_BASE + 0x1800, (
            f"row {row} col 0 line 0 should land inside the 6144-byte pixel area"
        )


class TestDecodeScreenCell:

    def test_blank_cell_is_zero(self):
        assert decode_screen_cell(bytearray(65536), 0, 0) == 0, (
            "all-zero cell should decode to 0"
        )

    @pytest.mark.parametrize("char", [0, 32, 65, 90, 122, 127, 255])
    def test_uniform_cell_decodes_to_its_byte(self, char):
        mem = bytearray(65536)
        for line in range(8):
            mem[screen_addr(0, 0, line)] = char
        assert decode_screen_cell(mem, 0, 0) == char, (
            f"uniform cell of {char} should decode to {char}"
        )

    def test_inconsistent_cell_raises(self):
        mem = bytearray(65536)
        mem[screen_addr(0, 0, 0)] = 65
        mem[screen_addr(0, 0, 1)] = 66
        with pytest.raises(ValueError, match="inconsistent"):
            decode_screen_cell(mem, 0, 0)

    def test_distinct_cells_do_not_cross_contaminate(self):
        mem = bytearray(65536)
        for line in range(8):
            mem[screen_addr(0, 0, line)] = 65
            mem[screen_addr(0, 1, line)] = 66
        assert decode_screen_cell(mem, 0, 0) == 65, "cell (0,0) should decode to 65"
        assert decode_screen_cell(mem, 0, 1) == 66, "cell (0,1) should decode to 66"


class TestTestFont:

    def test_covers_chars_32_to_127(self):
        assert len(TEST_FONT) == 96 * 8, (
            "TEST_FONT should cover 96 chars (32..127), 8 bytes each"
        )

    @pytest.mark.parametrize("char", [32, 33, 65, 90, 122, 127])
    def test_identity_layout(self, char):
        offset = (char - 32) * 8
        assert TEST_FONT[offset:offset + 8] == bytes([char] * 8), (
            f"TEST_FONT entry for char {char} should be 8 copies of {char}"
        )

    def test_base_address_matches_rom_font(self):
        assert SPECTRUM_FONT_BASE == 0x3D00, (
            "Spectrum ROM font base should be $3D00"
        )


class TestFontPreloaded:

    def test_font_loaded_at_font_base(self, fm):
        fm.run([])
        mem = fm._last_m.mem
        offset = (65 - 32) * 8
        start = SPECTRUM_FONT_BASE + offset
        assert bytes(mem[start:start + 8]) == bytes([65] * 8), (
            "after execute, font for 'A' should be 8 copies of 65 at $3D00 + (65-32)*8"
        )

    def test_font_occupies_full_range(self, fm):
        fm.run([])
        mem = fm._last_m.mem
        assert bytes(mem[SPECTRUM_FONT_BASE:SPECTRUM_FONT_BASE + len(TEST_FONT)]) == TEST_FONT, (
            "TEST_FONT should be loaded verbatim at SPECTRUM_FONT_BASE"
        )

    def test_last_m_is_none_before_run(self):
        fm = ForthMachine()
        assert fm._last_m is None, (
            "a fresh ForthMachine should have no captured machine yet"
        )


class TestForthResultCharsOut:

    def test_default_is_empty_bytes(self):
        result = ForthResult(data_stack=[])
        assert result.chars_out == b"", (
            "ForthResult.chars_out should default to empty bytes"
        )

    def test_empty_program_yields_empty_chars_out(self, fm):
        assert fm.run([]).chars_out == b"", (
            "a program that emits nothing should yield empty chars_out"
        )

    def test_border_program_yields_empty_chars_out(self, fm):
        result = fm.run([fm.label("LIT"), 3, fm.label("BORDER")])
        assert result.chars_out == b"", (
            "BORDER writes should not appear in chars_out"
        )
