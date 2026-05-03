"""
Tests for `w:` / `c:` / `b:` array literal openers and the `;` closer that
auto-counts array length and patches the count slot in the array header.
Layout: [count, 16-bit][data...]. `;w` cells, `;c` bytes, `;b` packs bits.
"""
from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler, CompileError


def _build(source: str) -> tuple[Compiler, bytes]:
    c = Compiler()
    c.compile_source(source + "\n: main halt ;")
    c.compile_main_call()
    return c, c.build()


def _read_cell(image: bytes, addr: int, origin: int) -> int:
    o = addr - origin
    return image[o] | (image[o + 1] << 8)


class TestWordArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("w: xs ;",                            0),
        ("w: xs 10 , ;",                       1),
        ("w: xs 10 , 20 , 30 , ;",             3),
        ("w: xs 1 , 2 , 3 , 4 , 5 , 6 , 7 , ;", 7),
    ])
    def test_count_matches_number_of_cells(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["xs"].data_address, c.origin) == expected, (
            f"w: ... ; should patch count slot to number of cells written ({expected})"
        )

    def test_cells_emitted_in_source_order(self):
        c, img = _build("w: xs 10 , 20 , 30 , ;")
        addr = c.words["xs"].data_address
        cells = [_read_cell(img, addr + 2 + 2 * i, c.origin) for i in range(3)]
        assert cells == [10, 20, 30], (
            "cells should follow the count slot in the order they were written"
        )

    def test_misaligned_byte_count_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="not a multiple of element size"):
            c.compile_source("w: xs $A c, ;")

    @pytest.mark.parametrize("source, expected", [
        ("w: xs $1 c, $0 c, ;",                 1),
        ("w: xs $1 c, $0 c, $2 c, $0 c, ;",     2),
    ])
    def test_even_c_comma_count_is_allowed(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["xs"].data_address, c.origin) == expected, (
            f"w: ... c, ; with even byte count should give cell count {expected}"
        )


class TestCharArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("c: bs ;",                                          0),
        ("c: bs $A0 c, ;",                                   1),
        ("c: bs $A0 c, $A1 c, $A2 c, $A3 c, ;",              4),
    ])
    def test_c_comma_count_matches_byte_count(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["bs"].data_address, c.origin) == expected, (
            f"c: ... ; with c, deposits should give count {expected}"
        )

    @pytest.mark.parametrize("source, expected", [
        ("c: bs 23 , ;",                  2),
        ("c: bs 23 , 43 , ;",             4),
        ("c: bs 3403 , 3321 , 555 , ;",   6),
    ])
    def test_comma_count_is_two_bytes_per_cell(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["bs"].data_address, c.origin) == expected, (
            f"c: ... , ; should give count {expected} (each , is 2 bytes)"
        )

    def test_mixed_comma_and_c_comma_in_char_array(self):
        c, img = _build("c: bs $A0 c, 23 , $B0 c, ;")
        assert _read_cell(img, c.words["bs"].data_address, c.origin) == 4, (
            "c: ... ; should sum bytes regardless of deposit form (1+2+1=4)"
        )

    def test_bytes_emitted_in_source_order(self):
        c, img = _build("c: bs $A0 c, $A1 c, $A2 c, $A3 c, ;")
        addr = c.words["bs"].data_address
        offset = addr - c.origin
        bytes_after_count = list(img[offset + 2:offset + 6])
        assert bytes_after_count == [0xA0, 0xA1, 0xA2, 0xA3], (
            "bytes should follow the count slot in source order"
        )


class TestBitArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("b: fs ;",                          0),
        ("b: fs $55 c, ;",                   8),
        ("b: fs $55 c, $AA c, ;",           16),
        ("b: fs $00 c, $00 c, $00 c, ;",    24),
    ])
    def test_c_comma_count_is_bytes_times_eight(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["fs"].data_address, c.origin) == expected, (
            f"b: ... c, ; should report bit count {expected} (bytes * 8)"
        )

    @pytest.mark.parametrize("source, expected", [
        ("b: fs 23 , ;",            16),
        ("b: fs 23 , 43 , ;",       32),
        ("b: fs 1 , 2 , 3 , 4 , ;", 64),
    ])
    def test_comma_count_is_two_bytes_per_cell_times_eight(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["fs"].data_address, c.origin) == expected, (
            f"b: ... , ; should report bit count {expected} (each , is 2 bytes = 16 bits)"
        )

    @pytest.mark.parametrize("source, expected", [
        ("b: fs $55 c, 23 , ;",     24),
        ("b: fs 23 , $AA c, ;",     24),
        ("b: fs 1 , 2 c, 3 , ;",    40),
    ])
    def test_mixed_comma_and_c_comma_in_bit_array(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["fs"].data_address, c.origin) == expected, (
            f"b: ... ; should accept any mix of , and c, ({expected} bits)"
        )


class TestExistingBehaviorPreserved:

    def test_force_inline_colon_still_works(self):
        c, _ = _build(":: dbl ( n -- 2n ) dup + ;")
        assert "dbl" in c.words, ":: ... ; force-inline colon should still define"
        assert c.words["dbl"].force_inline, "dbl should be marked force_inline"

    def test_regular_colon_still_works(self):
        c, _ = _build(": twice ( n -- 2n ) 2* ;")
        assert "twice" in c.words, ": ... ; regular colon should still define"

    def test_bare_semicolon_at_top_level_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="unexpected word ';'"):
            c.compile_source("; ")


class TestArrayLiteralErrors:

    def test_nested_array_literal_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="nested array literal"):
            c.compile_source("w: xs w: ys 1 , ; ;")

    def test_array_literal_inside_colon_definition_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="must be at top level"):
            c.compile_source(": foo  w: bad 1 , ;  ;")

    @pytest.mark.parametrize("opener", ["w:", "c:", "b:"])
    def test_opener_at_end_of_input_errors(self, opener):
        c = Compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source(opener)


class TestAccessibleAtRuntime:

    def test_warray_count_readable_via_at_fetch(self):
        c, img = _build(
            "w: xs 100 , 200 , 300 , ;\n"
            "variable result\n"
            ": main xs @ result ! halt ;"
        )
        c2 = Compiler()
        c2.compile_source(
            "w: xs 100 , 200 , 300 , ;\n"
            "variable result\n"
            ": main xs @ result ! halt ;"
        )
        c2.compile_main_call()
        from zt.sim import Z80
        image = c2.build()
        m = Z80()
        m.load(c2.origin, image)
        m.pc = c2.words["_start"].address
        m.run(max_ticks=10_000)
        result_addr = c2.words["result"].data_address
        count = m.mem[result_addr] | (m.mem[result_addr + 1] << 8)
        assert count == 3, (
            "runtime read of xs should return the auto-counted cell count of 3"
        )
