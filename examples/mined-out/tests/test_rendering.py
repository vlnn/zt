"""
Screen-level integration tests that verify glyphs actually land on the
Spectrum screen for two recent fixes:

  1. Wind actor leaves a flashing tilde at the expected trail position.
  2. Spreader-dropped mines render immediately when the cheat is active.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_ATTR_BASE,
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    screen_addr,
)


EXAMPLE_DIR = Path(__file__).parent.parent


def _run(harness: str) -> tuple[Compiler, Z80]:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.compile_source(harness)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=5_000_000)
    assert m.halted, "harness should halt"
    return c, m


WIND_HARNESS = """
require app/mined.fs

: main
    1 seed!
    5 level-no !
    init-level
    10 5  pack-xy trail-push
    11 5  pack-xy trail-push
    12 5  pack-xy trail-push
    13 5  pack-xy trail-push
    14 5  pack-xy trail-push
    602 ti !
    tick-wind
    halt ;
"""


class TestWindRendering:

    def test_wind_glyph_on_screen(self):
        _, m = _run(WIND_HARNESS)
        tilde_byte = m.mem[screen_addr(5, 10, 0)]
        assert tilde_byte == 0x7e, (
            f"wind should draw tilde (0x7e) at trail[0]=(10,5); "
            f"got 0x{tilde_byte:02x}"
        )

    def test_wind_attr_is_flashing_bright(self):
        _, m = _run(WIND_HARNESS)
        attr = m.mem[SPECTRUM_ATTR_BASE + 5 * 32 + 10]
        assert attr == 248, (
            f"wind cell should have FLASH|BRIGHT|PAPER=7|INK=0 (=248); "
            f"got {attr}"
        )


SPREADER_NO_CHEAT_HARNESS = """
require app/mined.fs

: main
    1 seed!
    3 level-no !
    init-level
    10 spreader-row !   3 spreader-col !   1 spreader-active !
    30 0 do
        spreader-active @ 0= if leave then
        spreader-step
    loop
    halt ;
"""

SPREADER_WITH_CHEAT_HARNESS = """
require app/mined.fs

: main
    1 seed!
    3 level-no !
    init-level
    -1 0 cheat-observe   1 0 cheat-observe
    10 spreader-row !   3 spreader-col !   1 spreader-active !
    30 0 do
        spreader-active @ 0= if leave then
        spreader-step
    loop
    halt ;
"""


def _count_mine_glyphs(m: Z80, rows: tuple[int, ...]) -> int:
    count = 0
    for row in rows:
        for col in range(32):
            if m.mem[screen_addr(row, col, 0)] == 0x2a:
                count += 1
    return count


class TestSpreaderMineVisibility:

    def test_spreader_mines_always_visible(self):
        _, m = _run(SPREADER_NO_CHEAT_HARNESS)
        visible = _count_mine_glyphs(m, (9, 10, 11))
        assert visible > 0, (
            "spreader-dropped mines should be drawn immediately as the "
            "spreader walks, matching BASIC line 115 behavior"
        )

    def test_spreader_mines_visible_with_cheat_too(self):
        _, m = _run(SPREADER_WITH_CHEAT_HARNESS)
        visible = _count_mine_glyphs(m, (9, 10, 11))
        assert visible > 0, (
            "spreader-dropped mines stay visible with cheat fired as well"
        )


BILL_SCROLL_HARNESS = """
require app/mined.fs

: main
    intro-colors
    init-bill-scroll
    0 6 bill-scroll-frame
    10 6 bill-scroll-frame
    15 6 bill-scroll-frame
    halt ;
"""


class TestBillScrollAnimation:

    def _run_and_read_row_top(self, row: int, length: int = 32) -> bytes:
        _, m = _run(BILL_SCROLL_HARNESS)
        out = bytearray()
        for col in range(length):
            out.append(m.mem[screen_addr(row, col, 0)])
        return bytes(out)

    def test_bill_scroll_frame_places_player_glyph_somewhere(self):
        row6 = self._run_and_read_row_top(6, 32)
        assert 0x4f in row6, (
            "after sequential bill-scroll-frame calls ending at offset 10, "
            "the player glyph 0x4f should appear somewhere on row 6"
        )

    def test_bill_scroll_frame_places_bug_glyph_somewhere(self):
        row6 = self._run_and_read_row_top(6, 32)
        assert 0x40 in row6, (
            "bug glyph 0x40 should appear on row 6 after scroll frames advance"
        )
