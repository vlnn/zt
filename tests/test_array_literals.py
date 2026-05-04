"""
Tests for `w:` / `c:` / `b:` array literal openers and the `;` closer.

Inside an array literal, every literal number, constant, or `' word`
reference is auto-emitted at the array's natural granularity:
  c: emits 1 byte per item (validated -128..255)
  w: emits 2 bytes per item (validated -32768..65535)
  b: packs 1 bit per item (only 0 or 1)
The count slot at offset 0 records the number of items, not bytes.

Layout: [count: 16-bit][data...].
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


def _read_byte(image: bytes, addr: int, origin: int) -> int:
    return image[addr - origin]


class TestWordArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("w: xs ;",                         0),
        ("w: xs 10 ;",                      1),
        ("w: xs 10 20 30 ;",                3),
        ("w: xs 1 2 3 4 5 6 7 ;",           7),
    ])
    def test_count_matches_number_of_cells(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["xs"].data_address, c.origin) == expected, (
            f"w: ... ; count slot should equal the number of cells written "
            f"({expected})"
        )

    def test_cells_emitted_in_source_order(self):
        c, img = _build("w: xs 10 20 30 ;")
        addr = c.words["xs"].data_address
        cells = [_read_cell(img, addr + 2 + 2 * i, c.origin) for i in range(3)]
        assert cells == [10, 20, 30], (
            "w: cells should follow the count slot in source order"
        )

    @pytest.mark.parametrize("value", [-32768, -1, 0, 1, 32767, 65535])
    def test_word_range_accepted(self, value):
        c, img = _build(f"w: xs {value} ;")
        addr = c.words["xs"].data_address
        cell = _read_cell(img, addr + 2, c.origin)
        assert cell == (value & 0xFFFF), (
            f"w: should accept {value} and store its 16-bit two's complement"
        )

    @pytest.mark.parametrize("value", [-32769, 65536, 100_000])
    def test_word_out_of_range_errors(self, value):
        c = Compiler()
        with pytest.raises(CompileError, match="must fit in 16 bits"):
            c.compile_source(f"w: xs {value} ;")

    def test_constant_in_word_array_emits_value(self):
        c, img = _build("123 constant pi w: xs pi pi ;")
        addr = c.words["xs"].data_address
        assert _read_cell(img, addr, c.origin) == 2, "two cells written"
        assert _read_cell(img, addr + 2, c.origin) == 123, "first cell is pi"
        assert _read_cell(img, addr + 4, c.origin) == 123, "second cell is pi"

    def test_tick_in_word_array_emits_xt(self):
        c, img = _build(": foo ; w: xs ' foo ;")
        addr = c.words["xs"].data_address
        cell = _read_cell(img, addr + 2, c.origin)
        assert cell == c.words["foo"].address, (
            "' foo inside w: should emit foo's xt as the cell value"
        )


class TestCharArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("c: bs ;",                            0),
        ("c: bs $A0 ;",                        1),
        ("c: bs $A0 $A1 $A2 $A3 ;",            4),
    ])
    def test_count_matches_byte_count(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["bs"].data_address, c.origin) == expected, (
            f"c: ... ; count slot should equal the number of bytes ({expected})"
        )

    def test_bytes_emitted_in_source_order(self):
        c, img = _build("c: bs $A0 $A1 $A2 $A3 ;")
        addr = c.words["bs"].data_address
        bytes_after_count = [
            _read_byte(img, addr + 2 + i, c.origin) for i in range(4)
        ]
        assert bytes_after_count == [0xA0, 0xA1, 0xA2, 0xA3], (
            "bytes should follow the count slot in source order"
        )

    @pytest.mark.parametrize("value", [-128, -1, 0, 1, 127, 255])
    def test_byte_range_accepted(self, value):
        c, img = _build(f"c: bs {value} ;")
        addr = c.words["bs"].data_address
        byte = _read_byte(img, addr + 2, c.origin)
        assert byte == (value & 0xFF), (
            f"c: should accept {value} and store its 8-bit two's complement"
        )

    @pytest.mark.parametrize("value", [-129, 256, 1000])
    def test_byte_out_of_range_errors(self, value):
        c = Compiler()
        with pytest.raises(CompileError, match="must fit in a byte"):
            c.compile_source(f"c: bs {value} ;")


class TestBitArrayLiteral:

    @pytest.mark.parametrize("source, expected", [
        ("b: fs ;",                                                      0),
        ("b: fs 1 ;",                                                    1),
        ("b: fs 1 0 1 0 1 0 1 0 ;",                                      8),
        ("b: fs 1 0 1 0 1 0 1 0  0 1 0 1 0 1 0 1  1 1 1 1 0 0 0 0 ;",   24),
    ])
    def test_count_is_bit_count(self, source, expected):
        c, img = _build(source)
        assert _read_cell(img, c.words["fs"].data_address, c.origin) == expected, (
            f"b: ... ; count slot should equal the number of bits ({expected})"
        )

    def test_bits_packed_lsb_first(self):
        c, img = _build("b: fs 1 0 1 0 1 0 1 0 ;")
        addr = c.words["fs"].data_address
        first_byte = _read_byte(img, addr + 2, c.origin)
        assert first_byte == 0x55, (
            f"bits 1 0 1 0 1 0 1 0 should pack LSB-first as 0x55, got "
            f"0x{first_byte:02X}"
        )

    def test_partial_byte_padded_at_close(self):
        c, img = _build("b: fs 1 1 1 ;")
        addr = c.words["fs"].data_address
        assert _read_cell(img, addr, c.origin) == 3, "count records 3 bits"
        assert _read_byte(img, addr + 2, c.origin) == 0b00000111, (
            "trailing bits should be zero-padded into the final byte"
        )

    @pytest.mark.parametrize("value", [-1, 2, 5, 256])
    def test_non_bit_value_errors(self, value):
        c = Compiler()
        with pytest.raises(CompileError, match="accepts only 0 or 1"):
            c.compile_source(f"b: fs {value} ;")


class TestArrayLiteralForbiddenContents:

    @pytest.mark.parametrize("opener", ["c:", "w:", "b:"])
    def test_colon_word_inside_array_errors(self, opener):
        c = Compiler()
        body = "1 0 1 0 1 0 1 0" if opener == "b:" else "1 2 3"
        with pytest.raises(CompileError, match="unexpected word"):
            c.compile_source(f": helper ; {opener} xs {body} helper ;")

    @pytest.mark.parametrize("opener", ["c:", "b:"])
    def test_tick_outside_word_array_errors(self, opener):
        c = Compiler()
        with pytest.raises(CompileError, match="only allowed inside w: arrays"):
            c.compile_source(f": foo ; {opener} xs ' foo ;")

    def test_old_c_comma_form_no_longer_works(self):
        c = Compiler()
        with pytest.raises(CompileError):
            c.compile_source("c: bs 1 c, 2 c, ;")

    def test_old_comma_form_no_longer_works(self):
        c = Compiler()
        with pytest.raises(CompileError):
            c.compile_source("w: xs 1 , 2 , ;")


class TestArrayLiteralStructure:

    def test_nested_array_literal_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="nested array literal"):
            c.compile_source("w: xs w: ys 1 ; ;")

    def test_array_literal_inside_colon_definition_errors(self):
        c = Compiler()
        with pytest.raises(CompileError, match="must be at top level"):
            c.compile_source(": foo  w: bad 1 ;  ;")

    @pytest.mark.parametrize("opener", ["w:", "c:", "b:"])
    def test_opener_at_end_of_input_errors(self, opener):
        c = Compiler()
        with pytest.raises(CompileError, match="unexpected end of input"):
            c.compile_source(opener)


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


class TestAccessibleAtRuntime:

    def test_warray_count_readable_via_at_fetch(self):
        c = Compiler()
        c.compile_source(
            "w: xs 100 200 300 ;\n"
            "variable result\n"
            ": main xs @ result ! halt ;"
        )
        c.compile_main_call()
        from zt.sim import Z80
        image = c.build()
        m = Z80()
        m.load(c.origin, image)
        m.pc = c.words["_start"].address
        m.run(max_ticks=10_000)
        result_addr = c.words["result"].data_address
        count = m.mem[result_addr] | (m.mem[result_addr + 1] << 8)
        assert count == 3, (
            "runtime read of xs should return the auto-counted cell count of 3"
        )
