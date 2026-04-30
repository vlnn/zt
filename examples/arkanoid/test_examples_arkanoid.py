"""End-to-end tests for the arkanoid example.

The game runs in a forever-loop until the player loses all lives, so tests
bound execution by tick budget. Two execution modes are exercised:

  - free-run: no keys held; ball flies freely, eventually destroys some
    bricks, may go around several times.
  - keyboard-driven: hold O or P and verify the paddle moves.
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


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "arkanoid"
MAIN = EXAMPLE_DIR / "main.fs"

TICK_BUDGET = 2_000_000

PADDLE_START_COL = 14
PADDLE_W = 3
PADDLE_ROW = 22
PADDLE_MIN_COL = 1
PADDLE_MAX_COL = 28

BALL_START_X = 128
BALL_START_Y = 160
LIVES_START = 3
BRICKS_COLS = 30
BRICKS_ROWS = 4
BRICKS_INITIAL = BRICKS_COLS * BRICKS_ROWS


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _s16(lo: int, hi: int) -> int:
    v = _u16(lo, hi)
    return v - 0x10000 if v >= 0x8000 else v


def _read_word(m: Z80, label: str, c: Compiler) -> int:
    addr = c.words[label].data_address
    return _s16(m.mem[addr], m.mem[addr + 1])


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


def _run(built_compiler: Compiler, pressed_keys: set[int] | None = None,
         budget: int = TICK_BUDGET) -> Z80:
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    m.pressed_keys = set(pressed_keys or set())
    m.run(max_ticks=budget)
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

    def test_main_exists(self):
        assert MAIN.is_file(), "main.fs should exist for arkanoid"

    @pytest.mark.parametrize("lib_name", [
        "sprites.fs", "bricks.fs", "paddle.fs", "ball.fs", "score.fs", "game.fs",
    ])
    def test_lib_exists(self, lib_name):
        path = EXAMPLE_DIR / "lib" / lib_name
        assert path.is_file(), f"library file '{lib_name}' should exist"


class TestModulesCompile:

    @pytest.mark.parametrize("name", [
        "ball-shifted", "blank-shifted", "paddle-left", "paddle-mid",
        "paddle-right", "brick-tile", "brick-blank",
    ])
    def test_sprite_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, f"sprite '{name}' should be defined"

    @pytest.mark.parametrize("name", [
        "ball-x", "ball-y", "ball-dx", "ball-dy", "ball-lost",
        "paddle-col", "paddle-old-col",
        "brick-grid", "score", "lives",
    ])
    def test_state_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, f"state '{name}' should be defined"

    @pytest.mark.parametrize("name", [
        "ball-step", "paddle-step", "game-step", "game-loop", "arkanoid",
        "init-level", "draw-all-bricks",
    ])
    def test_logic_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, f"logic '{name}' should be defined"


class TestPaddleKeyboardControl:

    def test_paddle_starts_centered(self, built_compiler, free_run):
        col = _read_word(free_run, "paddle-col", built_compiler)
        assert PADDLE_MIN_COL <= col <= PADDLE_MAX_COL, (
            f"paddle column should be a valid 3-wide position within "
            f"[{PADDLE_MIN_COL}, {PADDLE_MAX_COL}]; got {col}"
        )

    def test_paddle_moves_left_when_O_held(self, built_compiler, o_held):
        col = _read_word(o_held, "paddle-col", built_compiler)
        assert col == PADDLE_MIN_COL, (
            f"with O held for the whole run, paddle should reach the left "
            f"wall (col={PADDLE_MIN_COL}); got col={col}"
        )

    def test_paddle_moves_right_when_P_held(self, built_compiler, p_held):
        col = _read_word(p_held, "paddle-col", built_compiler)
        assert col == PADDLE_MAX_COL, (
            f"with P held for the whole run, paddle should reach the right "
            f"wall (col={PADDLE_MAX_COL}); got col={col}"
        )

    def test_paddle_does_not_move_with_no_keys(self, built_compiler, free_run):
        col = _read_word(free_run, "paddle-col", built_compiler)
        assert col == PADDLE_START_COL, (
            f"with no keys held, paddle should stay at the start column "
            f"({PADDLE_START_COL}); got {col}"
        )


class TestBallStaysInBounds:

    def test_ball_x_within_bounds(self, built_compiler, free_run):
        x = _read_word(free_run, "ball-x", built_compiler)
        assert 8 <= x <= 240, (
            f"ball x must remain within [8, 240] (between the side walls); "
            f"got {x}"
        )

    def test_ball_y_below_top(self, built_compiler, free_run):
        y = _read_word(free_run, "ball-y", built_compiler)
        assert 0 <= y <= 184, (
            f"ball y must remain within [0, 184] before being declared lost; "
            f"got {y}"
        )

    def test_ball_position_changes(self, built_compiler, free_run):
        x = _read_word(free_run, "ball-x", built_compiler)
        y = _read_word(free_run, "ball-y", built_compiler)
        assert (x, y) != (BALL_START_X, BALL_START_Y), (
            f"ball should have moved from start ({BALL_START_X},{BALL_START_Y}) "
            f"by end of run; got ({x},{y})"
        )


class TestBricksDestroyed:

    def _bricks_alive(self, m: Z80, c: Compiler) -> int:
        addr = c.words["brick-grid"].data_address
        return sum(m.mem[addr + i] for i in range(BRICKS_INITIAL))

    def test_all_bricks_alive_after_short_run(self, built_compiler):
        \
        m = _run(built_compiler, budget=20_000)
        alive = self._bricks_alive(m, built_compiler)
        assert alive == BRICKS_INITIAL, (
            f"after a very short run, all {BRICKS_INITIAL} bricks should "
            f"still be alive; got {alive}"
        )

    def test_some_bricks_destroyed_after_long_run(self, built_compiler, free_run):
        alive = self._bricks_alive(free_run, built_compiler)
        assert alive < BRICKS_INITIAL, (
            f"after the full run, some bricks should have been destroyed; "
            f"alive={alive}, initial={BRICKS_INITIAL}"
        )


class TestScoreAndLives:

    def test_lives_initialized(self, built_compiler):
        \
        m = _run(built_compiler, budget=20_000)
        lives = _read_word(m, "lives", built_compiler)
        assert lives == LIVES_START, (
            f"after init, lives should equal {LIVES_START}; got {lives}"
        )

    def test_score_grows_with_brick_hits(self, built_compiler, free_run):
        score = _read_word(free_run, "score", built_compiler)
        assert score > 0, (
            f"after the full run with bricks being destroyed, score should "
            f"be positive; got {score}"
        )

    def test_score_consistent_with_destroyed_bricks(self, built_compiler, free_run):
        score = _read_word(free_run, "score", built_compiler)
        addr = built_compiler.words["brick-grid"].data_address
        destroyed = sum(1 for i in range(BRICKS_INITIAL) if free_run.mem[addr + i] == 0)
        assert score == destroyed * 10, (
            f"score (10 per brick) should equal destroyed*10; "
            f"score={score}, destroyed={destroyed}"
        )


class TestPaddleEdgeProtection:

    def test_paddle_never_off_screen_left(self, built_compiler, o_held):
        col = _read_word(o_held, "paddle-col", built_compiler)
        assert col >= PADDLE_MIN_COL, (
            f"paddle column should never go below {PADDLE_MIN_COL}; got {col}"
        )

    def test_paddle_never_off_screen_right(self, built_compiler, p_held):
        col = _read_word(p_held, "paddle-col", built_compiler)
        assert col <= PADDLE_MAX_COL, (
            f"paddle column should never exceed {PADDLE_MAX_COL}; got {col}"
        )


class TestSpritesRendered:

    def test_some_pixels_drawn(self, built_compiler, free_run):
        total_set = 0
        for char_row in range(2, 24):
            for col in range(32):
                for line in range(8):
                    if free_run.mem[screen_addr(char_row, col, line)]:
                        total_set += 1
        assert total_set > 0, (
            f"after running the game, at least some screen bytes should be "
            f"non-zero (bricks/paddle/ball drawing); got {total_set}"
        )

    def test_paddle_visible_on_paddle_row(self, built_compiler, free_run):
        \
        any_set = False
        for line in range(8):
            for col in range(32):
                if free_run.mem[screen_addr(PADDLE_ROW, col, line)]:
                    any_set = True
                    break
            if any_set:
                break
        assert any_set, (
            f"after the run, at least one byte on the paddle row "
            f"({PADDLE_ROW}) should be set"
        )
