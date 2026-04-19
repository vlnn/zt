"""
Exercises the plain-6789 and CAPS+5678 cursor-key mapping in the
mined-out actors module. Simulates held keys via pressed_keys and
reads the sign of read-dx / read-dy through EMIT.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    _read_data_stack,
    decode_screen_text,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "mined-out"
CAPS_CODE = 0x01


HARNESS = """
require app/actors.fs

: emit-dx   ( dx -- )
    dup -1 = if drop 76 emit exit then    \\ L
    dup  1 = if drop 82 emit exit then    \\ R
    drop 46 emit ;                        \\ .

: emit-dy   ( dy -- )
    dup -1 = if drop 85 emit exit then    \\ U
    dup  1 = if drop 68 emit exit then    \\ D
    drop 46 emit ;                        \\ .

: main      read-dx emit-dx  read-dy emit-dy  halt ;
"""


def _run_with_keys(pressed: set[int]) -> bytes:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.compile_source(HARNESS)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pressed_keys = set(pressed)
    m.pc = c.words["_start"].address
    m.run(max_ticks=2_000_000)
    assert m.halted, "harness should halt"

    _read_data_stack(m, c.data_stack_top, False)
    row = m.mem[c.asm.labels["_emit_cursor_row"]]
    col = m.mem[c.asm.labels["_emit_cursor_col"]]
    return decode_screen_text(m.mem, row, col)


class TestMinedOutCursorKeys:

    @pytest.mark.parametrize("pressed,expected,label", [
        (set(),                         b"..",  "no keys → neutral"),
        ({ord("6")},                    b"L.",  "plain 6 → left"),
        ({ord("7")},                    b"R.",  "plain 7 → right"),
        ({ord("9")},                    b".U",  "plain 9 → up"),
        ({ord("8")},                    b".D",  "plain 8 → down"),
        ({CAPS_CODE, ord("5")},         b"L.",  "CAPS+5 → left"),
        ({CAPS_CODE, ord("8")},         b"R.",  "CAPS+8 → right"),
        ({CAPS_CODE, ord("7")},         b".U",  "CAPS+7 → up"),
        ({CAPS_CODE, ord("6")},         b".D",  "CAPS+6 → down"),
        ({CAPS_CODE},                   b"..",  "CAPS alone → neutral"),
        ({ord("6"), ord("7")},          b"..",  "plain 6+7 cancel to zero dx"),
        ({ord("8"), ord("9")},          b"..",  "plain 8+9 cancel to zero dy"),
    ])
    def test_read_dx_dy(self, pressed, expected, label):
        got = _run_with_keys(pressed)
        assert got == expected, (
            f"{label} should emit {expected!r}; got {got!r}"
        )

    def test_caps_6_is_down_not_left(self):
        assert _run_with_keys({CAPS_CODE, ord("6")}) == b".D", (
            "CAPS+6 should read as Down only (not also Left from the plain-6 "
            "mapping); otherwise CAPS-held cursor moves would collide"
        )

    def test_caps_8_is_right_not_down(self):
        assert _run_with_keys({CAPS_CODE, ord("8")}) == b"R.", (
            "CAPS+8 should read as Right only (plain-8=Down must be gated "
            "off while CAPS is held)"
        )

    def test_caps_7_is_up_not_right(self):
        assert _run_with_keys({CAPS_CODE, ord("7")}) == b".U", (
            "CAPS+7 should read as Up only (plain-7=Right must be gated "
            "off while CAPS is held)"
        )


REPLAY_HARNESS = """
require app/hud.fs

: emit-frames  ( n -- )
    dup 3 = if drop 70 emit exit then    \\ F (fast/default)
    dup 10 = if drop 83 emit exit then   \\ S (slow)
    drop 63 emit ;                       \\ ?

: main  replay-frames emit-frames halt ;
"""


def _run_replay_frames(pressed: set[int]) -> bytes:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.compile_source(REPLAY_HARNESS)
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pressed_keys = set(pressed)
    m.pc = c.words["_start"].address
    m.run(max_ticks=2_000_000)
    assert m.halted, "harness should halt"

    _read_data_stack(m, c.data_stack_top, False)
    row = m.mem[c.asm.labels["_emit_cursor_row"]]
    col = m.mem[c.asm.labels["_emit_cursor_col"]]
    return decode_screen_text(m.mem, row, col)


class TestMinedOutReplaySpeed:

    def test_replay_default_is_fast(self):
        assert _run_replay_frames(set()) == b"F", (
            "replay-frames with no keys held should return 3 (default fast "
            "delay between replay frames)"
        )

    def test_replay_s_held_is_slow(self):
        assert _run_replay_frames({ord("S")}) == b"S", (
            "replay-frames with S held should return 10 for a slower replay"
        )

    def test_replay_other_key_ignored(self):
        assert _run_replay_frames({ord("Q")}) == b"F", (
            "replay-frames should only change behaviour for S; other keys "
            "leave the default fast speed"
        )


VALID_LEVEL_KEY_HARNESS = """
require app/menu.fs

: emit-flag  ( flag -- )
    if 89 emit exit then
    78 emit ;

: main
    9 max-level-reached !
    56 valid-level-key? emit-flag
     0 valid-level-key? emit-flag
    49 valid-level-key? emit-flag
    halt ;
"""


class TestMinedOutValidLevelKey:

    def test_valid_level_key_filters_shift_and_accepts_digits(self):
        c = Compiler(include_dirs=[EXAMPLE_DIR])
        c.compile_source(VALID_LEVEL_KEY_HARNESS)
        c.compile_main_call()
        image = c.build()

        m = Z80()
        m.load(c.origin, image)
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.run(max_ticks=2_000_000)
        assert m.halted, "harness should halt"

        _read_data_stack(m, c.data_stack_top, False)
        row = m.mem[c.asm.labels["_emit_cursor_row"]]
        col = m.mem[c.asm.labels["_emit_cursor_col"]]
        out = decode_screen_text(m.mem, row, col)
        assert out == b"YNY", (
            f"ASCII '8' (56) should be valid, 0 (CAPS) should be invalid, "
            f"ASCII '1' (49) should be valid; got {out!r}"
        )
