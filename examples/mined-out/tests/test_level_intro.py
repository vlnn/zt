"""
Regression tests for show-level-intro dispatch.

Locks in the contract that level-no -> banner text mapping is preserved:
levels 2,3,4,5,8,9 each print their own banner; levels 1,6,7 leave the
banner blank; initial-bonus-pending suppresses the banner entirely so
show-initial-bonus can run in its place.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80, decode_screen_cell


EXAMPLE_DIR = Path(__file__).parent.parent
BANNER_ROW = 22
BANNER_WIDTH = 32


def _run(harness_body: str) -> Z80:
    src = f"""
require app/hud.fs
: main
{harness_body}
    halt ;
"""
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.compile_source(src)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=5_000_000)
    assert m.halted, "harness should halt cleanly"
    return m


def _banner(m: Z80) -> bytes:
    chars = bytearray()
    for col in range(BANNER_WIDTH):
        ch = decode_screen_cell(m.mem, BANNER_ROW, col)
        chars.append(ch if ch else ord(" "))
    return bytes(chars).rstrip()


@pytest.mark.parametrize("level,expected_substring", [
    (2, b"rescue the damsels"),
    (3, b"watch out"),
    (4, b"a bug stalks"),
    (5, b"your map may blow"),
    (8, b"gap is closed"),
    (9, b"rescue bill"),
], ids=lambda v: str(v))
def test_show_level_intro_prints_matching_banner(level, expected_substring):
    m = _run(f"""
    7 0 cls
    0 initial-bonus-pending !
    {level} level-no !
    show-level-intro
""")
    banner = _banner(m)
    assert expected_substring in banner, (
        f"level {level} banner should contain {expected_substring!r}, "
        f"got {banner!r}"
    )


@pytest.mark.parametrize("level", [1, 6, 7], ids=lambda v: f"lvl{v}")
def test_show_level_intro_blank_for_levels_without_banner(level):
    m = _run(f"""
    7 0 cls
    0 initial-bonus-pending !
    {level} level-no !
    show-level-intro
""")
    banner = _banner(m)
    assert banner == b"", (
        f"level {level} should leave banner blank "
        f"(no entry in intro-levels), got {banner!r}"
    )


def test_show_level_intro_suppressed_when_initial_bonus_pending():
    m = _run("""
    7 0 cls
    1 initial-bonus-pending !
    2 level-no !
    show-level-intro
""")
    banner = _banner(m)
    assert banner == b"", (
        "show-level-intro should be a no-op when initial-bonus-pending "
        f"is set (so show-initial-bonus can run instead), got {banner!r}"
    )


def test_show_level_intro_clears_previous_banner():
    m = _run("""
    7 0 cls
    0 initial-bonus-pending !
    2 level-no !  show-level-intro
    1 level-no !  show-level-intro
""")
    banner = _banner(m)
    assert banner == b"", (
        "transitioning from a banner level to a no-banner level "
        f"should clear the banner row, got {banner!r}"
    )
