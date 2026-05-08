"""End-to-end check: holding a control key for many frames moves the angle.

The Forth-side `key-state` reads port $FE which the simulator synthesizes
from `pressed_keys`.  We can't test that from inside an `assert-eq` Forth
word, so this test boots the demo, holds a key for a fixed tick budget,
and reads the resulting `angle-yaw` / `angle-pitch` variables out of
memory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"

\
\
TICK_BUDGET = 5_000_000


@pytest.fixture(scope="module")
def built() -> Compiler:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


def _run(built: Compiler, pressed: set[int] = set()) -> Z80:
    image = built.build()
    m = Z80()
    m.load(built.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built.words["_start"].address
    m.pressed_keys = set(pressed)
    m.run(max_ticks=TICK_BUDGET)
    return m


def _read_signed_word(m: Z80, addr: int) -> int:
    v = m.mem[addr] | (m.mem[addr + 1] << 8)
    return v - 0x10000 if v >= 0x8000 else v


def _angle_yaw(built: Compiler, m: Z80) -> int:
    addr = built.words["angle-yaw"].data_address
    return _read_signed_word(m, addr)


def _angle_pitch(built: Compiler, m: Z80) -> int:
    addr = built.words["angle-pitch"].data_address
    return _read_signed_word(m, addr)


class TestNoKeysHeldKeepsAnglesAtZero:
    \

    def test_yaw_stays_zero(self, built):
        m = _run(built)
        assert _angle_yaw(built, m) == 0, (
            f"with no keys held, angle-yaw should stay 0, got {_angle_yaw(built, m)}"
        )

    def test_pitch_stays_zero(self, built):
        m = _run(built)
        assert _angle_pitch(built, m) == 0, (
            f"with no keys held, angle-pitch should stay 0, got {_angle_pitch(built, m)}"
        )


class TestYawKeysAdvanceYawNotPitch:
    \

    @pytest.mark.parametrize("key,expect_sign", [
        (ord("P"), 1),    \
        (ord("9"), 1),
        (ord("O"), -1),   \
        (ord("8"), -1),
    ])
    def test_yaw_key_moves_yaw(self, built, key, expect_sign):
        m = _run(built, pressed={key})
        yaw = _angle_yaw(built, m)
        assert yaw * expect_sign > 0, (
            f"key {chr(key)!r} should move yaw in direction {expect_sign:+d}, got {yaw}"
        )

    @pytest.mark.parametrize("key", [ord("P"), ord("9"), ord("O"), ord("8")])
    def test_yaw_key_leaves_pitch_zero(self, built, key):
        m = _run(built, pressed={key})
        assert _angle_pitch(built, m) == 0, (
            f"key {chr(key)!r} should not affect pitch, got {_angle_pitch(built, m)}"
        )


class TestPitchKeysAdvancePitchNotYaw:
    \

    @pytest.mark.parametrize("key,expect_sign", [
        (ord("A"), 1),
        (ord("6"), 1),
        (ord("Q"), -1),
        (ord("7"), -1),
    ])
    def test_pitch_key_moves_pitch(self, built, key, expect_sign):
        m = _run(built, pressed={key})
        pitch = _angle_pitch(built, m)
        assert pitch * expect_sign > 0, (
            f"key {chr(key)!r} should move pitch in direction {expect_sign:+d}, got {pitch}"
        )

    @pytest.mark.parametrize("key", [ord("A"), ord("6"), ord("Q"), ord("7")])
    def test_pitch_key_leaves_yaw_zero(self, built, key):
        m = _run(built, pressed={key})
        assert _angle_yaw(built, m) == 0, (
            f"key {chr(key)!r} should not affect yaw, got {_angle_yaw(built, m)}"
        )


class TestSpaceQuitsTheLoop:
    \

    def test_space_held_program_halts_quickly(self, built):
        m = _run(built, pressed={ord(" ")})
        \
        \
        assert m._ticks < TICK_BUDGET, (
            f"SPACE should make the loop exit; ran {m._ticks} ticks of {TICK_BUDGET}"
        )
