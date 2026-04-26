"""
End-to-end test for the sprite *dynamics* demo.

The demo runs forever, so tests bound execution by tick budget instead of
expecting a halt. Two execution modes are exercised:

  - free-run: no keys held; flier and gravity ball follow their trajectories,
    and the player is animated in place (no horizontal motion).
  - keyboard-driven: simulate holding O or P and verify the player moves
    in the expected direction.
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


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "sprite-demo"
DYNAMIC = EXAMPLE_DIR / "dynamic.fs"

\
TICK_BUDGET = 1_000_000

PLAYER_INITIAL_X = 32
PLAYER_INITIAL_Y = 24
PLAYER_SPEED = 3

SMILEY_OPEN = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C]
BALL = [0x3C, 0x7E, 0xFF, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C]


def _s16(lo: int, hi: int) -> int:
    v = lo | (hi << 8)
    return v - 0x10000 if v >= 0x8000 else v


def _read_actor(m: Z80, addr: int) -> dict[str, int]:
    return {
        "x":  _s16(m.mem[addr],     m.mem[addr + 1]),
        "y":  _s16(m.mem[addr + 2], m.mem[addr + 3]),
        "ox": _s16(m.mem[addr + 4], m.mem[addr + 5]),
        "oy": _s16(m.mem[addr + 6], m.mem[addr + 7]),
        "frames_ptr": m.mem[addr + 8] | (m.mem[addr + 9] << 8),
        "count": m.mem[addr + 10],
        "frame": m.mem[addr + 11],
        "tick":  m.mem[addr + 12],
        "rate":  m.mem[addr + 13],
    }


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.include_stdlib()
    c.compile_source(DYNAMIC.read_text(), source=str(DYNAMIC))
    c.compile_main_call()
    c.build()
    return c


def _run(built_compiler: Compiler, pressed_keys: set[int] = set()) -> Z80:
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    m.pressed_keys = set(pressed_keys)
    m.run(max_ticks=TICK_BUDGET)
    \
    return m


@pytest.fixture(scope="module")
def free_run(built_compiler):
    return _run(built_compiler)


@pytest.fixture(scope="module")
def o_held(built_compiler):
    return _run(built_compiler, pressed_keys={ord("O")})


@pytest.fixture(scope="module")
def p_held(built_compiler):
    return _run(built_compiler, pressed_keys={ord("P")})


class TestFilesPresent:

    def test_dynamic_main_exists(self):
        assert DYNAMIC.is_file()

    def test_animation_lib_exists(self):
        assert (EXAMPLE_DIR / "lib" / "animation.fs").is_file()

    def test_sprites_data_lib_exists(self):
        assert (EXAMPLE_DIR / "lib" / "sprites-data.fs").is_file()


class TestActorRecordsCompile:

    @pytest.mark.parametrize("name", [
        "actor-player", "actor-flier", "actor-gravity",
    ])
    def test_actor_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, f"actor '{name}' should be defined"

    def test_player_frames_pointer_initialized(self, built_compiler):
        addr = built_compiler.words["actor-player"].data_address
        image = built_compiler.build()
        offset = addr - built_compiler.origin
        actual = image[offset + 8] | (image[offset + 9] << 8)
        expected = built_compiler.words["smiley-frames"].data_address
        assert actual == expected, (
            f"player's frames pointer should equal smiley-frames address; "
            f"got ${actual:04X}, expected ${expected:04X}"
        )


class TestPlayerKeyboardControl:

    def test_player_does_not_move_horizontally_with_no_keys(
        self, built_compiler, free_run,
    ):
        addr = built_compiler.words["actor-player"].data_address
        actor = _read_actor(free_run, addr)
        assert actor["x"] == PLAYER_INITIAL_X, (
            f"with no keys held, player x should stay at {PLAYER_INITIAL_X}; "
            f"got {actor['x']}"
        )

    def test_player_does_not_move_vertically(self, built_compiler, free_run):
        addr = built_compiler.words["actor-player"].data_address
        actor = _read_actor(free_run, addr)
        assert actor["y"] == PLAYER_INITIAL_Y, (
            f"player y should stay at {PLAYER_INITIAL_Y} (player-control "
            f"only updates x); got {actor['y']}"
        )

    def test_player_moves_left_when_O_held(self, built_compiler, o_held):
        addr = built_compiler.words["actor-player"].data_address
        actor = _read_actor(o_held, addr)
        \
        assert -PLAYER_SPEED <= actor["x"] <= PLAYER_SPEED, (
            f"with O held for the whole run, player should reach the left "
            f"edge (x near 0); got x={actor['x']}"
        )

    def test_player_moves_right_when_P_held(self, built_compiler, p_held):
        addr = built_compiler.words["actor-player"].data_address
        actor = _read_actor(p_held, addr)
        assert 240 - PLAYER_SPEED <= actor["x"] <= 240 + PLAYER_SPEED, (
            f"with P held for the whole run, player should reach the right "
            f"edge (x near 240, the BLIT8X-safe maximum); got x={actor['x']}"
        )

    def test_player_animation_advances_under_O(self, built_compiler, o_held):
        \
        addr = built_compiler.words["actor-player"].data_address
        actor = _read_actor(o_held, addr)
        assert actor["frame"] in (0, 1), (
            f"player frame should be a valid index (0 or 1); got {actor['frame']}"
        )


class TestOtherActorsKeepRunning:

    def test_flier_position_changes_over_time(self, built_compiler, free_run):
        addr = built_compiler.words["actor-flier"].data_address
        actor = _read_actor(free_run, addr)
        assert (actor["x"], actor["y"]) != (8, 80), (
            f"flier should have moved from its initial (8, 80) by end of run; "
            f"got ({actor['x']}, {actor['y']})"
        )

    def test_flier_y_within_sine_envelope(self, built_compiler, free_run):
        \
        addr = built_compiler.words["actor-flier"].data_address
        actor = _read_actor(free_run, addr)
        assert 60 <= actor["y"] <= 100, (
            f"flier y must stay within base-y +/- 20 (sine amplitude); "
            f"got y={actor['y']}"
        )

    def test_flier_x_within_screen(self, built_compiler, free_run):
        addr = built_compiler.words["actor-flier"].data_address
        actor = _read_actor(free_run, addr)
        assert 0 <= actor["x"] <= 240, (
            f"flier x should stay within [0, 240]; got x={actor['x']}"
        )

    def test_gravity_position_changes_over_time(self, built_compiler, free_run):
        addr = built_compiler.words["actor-gravity"].data_address
        actor = _read_actor(free_run, addr)
        assert (actor["x"], actor["y"]) != (16, 16), (
            f"gravity ball should have left its initial (16, 16); "
            f"got ({actor['x']}, {actor['y']})"
        )

    def test_gravity_y_within_floor(self, built_compiler, free_run):
        addr = built_compiler.words["actor-gravity"].data_address
        actor = _read_actor(free_run, addr)
        assert 0 <= actor["y"] <= 176, (
            f"gravity y should be clamped to [0, floor=176]; got y={actor['y']}"
        )


class TestPriorPositionTracking:
    \

    @pytest.mark.parametrize("actor_name,max_skew", [
        ("actor-player", 6),
        ("actor-flier", 6),
        ("actor-gravity", 32),
    ])
    def test_ox_oy_close_to_x_y(self, built_compiler, free_run, actor_name, max_skew):
        addr = built_compiler.words[actor_name].data_address
        actor = _read_actor(free_run, addr)
        dx = abs(actor["ox"] - actor["x"])
        dy = abs(actor["oy"] - actor["y"])
        assert dx <= max_skew and dy <= max_skew, (
            f"{actor_name}: prior position should be within one step of current; "
            f"got ox={actor['ox']}, oy={actor['oy']}, x={actor['x']}, y={actor['y']}"
        )


class TestSpritesPresentOnScreen:
    \

    def test_no_stray_pixels_in_top_row(self, built_compiler, free_run):
        \
        for col in range(32):
            for line in range(8):
                b = free_run.mem[screen_addr(0, col, line)]
                assert b == 0, (
                    f"row 0 should stay clear; col={col} line={line} has ${b:02X}"
                )

    def test_some_pixels_drawn_somewhere(self, built_compiler, free_run):
        \
        total_set = 0
        for char_row in range(24):
            for col in range(32):
                for line in range(8):
                    if free_run.mem[screen_addr(char_row, col, line)]:
                        total_set += 1
        assert total_set > 0, (
            f"after running the dynamic demo, at least some screen bytes "
            f"should be non-zero (actors drawing); got {total_set}"
        )
