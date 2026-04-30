"""
End-to-end test for the sprite primitives demo: builds, runs, and verifies
that each primitive's output landed at the right place on the screen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    screen_addr,
)


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"

SMILEY = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C]


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


@pytest.fixture(scope="module")
def ran_machine(built_compiler: Compiler) -> Z80:
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    m.run(max_ticks=5_000_000)
    assert m.halted, "sprite demo should halt within the tick budget"
    return m


class TestCompiles:

    def test_example_files_exist(self):
        assert MAIN.is_file(), "examples/sprite-demo/main.fs should exist"
        assert (EXAMPLE_DIR / "lib" / "sprites-data.fs").is_file(), (
            "examples/sprite-demo/lib/sprites-data.fs should exist"
        )

    @pytest.mark.parametrize("word", [
        "smiley", "smiley-shifted",
        "ship-nose", "ship-body", "ship-tail", "ship-table",
        "demo-blit8", "demo-blit8c", "demo-blit8x", "demo-blit8xc", "demo-multi",
        "main",
    ])
    def test_word_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"sprite demo should define '{word}'"
        )


class TestBlit8RowOnScreen:

    @pytest.mark.parametrize("col", [4, 8, 12, 16])
    def test_smiley_pixels_present(self, ran_machine, col):
        for line in range(8):
            actual = ran_machine.mem[screen_addr(2, col, line)]
            assert actual == SMILEY[line], (
                f"BLIT8 smiley at (col={col},row=2) line {line} should hold "
                f"{SMILEY[line]:#04x}, got {actual:#04x}"
            )


class TestBlit8cRowOnScreen:

    @pytest.mark.parametrize("col,attr", [(4, 0x46), (8, 0x42), (12, 0x44), (16, 0x47)])
    def test_smiley_pixels_and_attr(self, ran_machine, col, attr):
        for line in range(8):
            actual = ran_machine.mem[screen_addr(5, col, line)]
            assert actual == SMILEY[line], (
                f"BLIT8C smiley pixels at (col={col},row=5) line {line} should hold "
                f"{SMILEY[line]:#04x}, got {actual:#04x}"
            )
        attr_addr = 0x5800 + 5 * 32 + col
        assert ran_machine.mem[attr_addr] == attr, (
            f"BLIT8C attr at (col={col},row=5) should hold {attr:#04x}"
        )


class TestBlit8xRowOnScreen:

    def test_byte_aligned_x_writes_left_col_only(self, ran_machine):
        for line in range(8):
            left = ran_machine.mem[screen_addr(8, 4, line)]
            right = ran_machine.mem[screen_addr(8, 5, line)]
            assert left == SMILEY[line], (
                f"BLIT8X x=32 y=64 line {line}: left col should be smiley byte"
            )
            assert right == 0, (
                f"BLIT8X x=32 y=64 line {line}: right col should be empty (shift=0)"
            )

    def test_pixel_shifted_splits_across_cols(self, ran_machine):
        for line in range(8):
            left = ran_machine.mem[screen_addr(8, 8, line)]
            right = ran_machine.mem[screen_addr(8, 9, line)]
            expected_left = SMILEY[line] >> 2
            expected_right = (SMILEY[line] << 6) & 0xFF
            assert left == expected_left, (
                f"BLIT8X x=66 (shift=2) line {line} left col: "
                f"expected {expected_left:#04x}, got {left:#04x}"
            )
            assert right == expected_right, (
                f"BLIT8X x=66 (shift=2) line {line} right col: "
                f"expected {expected_right:#04x}, got {right:#04x}"
            )


class TestMultiBlitSpaceshipOnScreen:

    NOSE = [0x07, 0x1F, 0x7F, 0xFF, 0xFF, 0x7F, 0x1F, 0x07]
    BODY = [0xFF, 0xFF, 0xFF, 0xE7, 0xE7, 0xFF, 0xFF, 0xFF]
    TAIL = [0xC0, 0xE0, 0xF8, 0xFC, 0xFC, 0xF8, 0xE0, 0xC0]

    @pytest.mark.parametrize("ship_x,base_col", [(16, 2), (80, 10)])
    def test_three_pieces_land_in_a_row(self, ran_machine, ship_x, base_col):
        for line in range(8):
            nose = ran_machine.mem[screen_addr(18, base_col, line)]
            body = ran_machine.mem[screen_addr(18, base_col + 1, line)]
            tail = ran_machine.mem[screen_addr(18, base_col + 2, line)]
            assert nose == self.NOSE[line], (
                f"ship at x={ship_x}: nose line {line} should be {self.NOSE[line]:#04x}"
            )
            assert body == self.BODY[line], (
                f"ship at x={ship_x}: body line {line} should be {self.BODY[line]:#04x}"
            )
            assert tail == self.TAIL[line], (
                f"ship at x={ship_x}: tail line {line} should be {self.TAIL[line]:#04x}"
            )
