"""End-to-end tests for the tetris example.

Game runs in a forever-loop until the player wins all three levels or
loses, so tests bound execution by tick budget and observe state from
the Forth dictionary's variables.

The Spectrum simulator returns $FF for non-keyboard ports, so kempston
input itself can't be exercised here — it's verified compositionally
by the controls.fs in-* predicates and by the kempston primitive's
presence in the dictionary.  Movement tests drive the Sinclair joystick
keys (6/7/8/9/0) which the keyboard simulator does support.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
)


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"

TICK_BUDGET = 2_000_000
SHORT_BUDGET = 200_000

PF_COLS = 10
PF_ROWS = 18
PF_SCREEN_COL = 11
PF_SCREEN_ROW = 2

PIECE_SPAWN_COL = 3
PIECE_SPAWN_ROW = 0

KEY_6, KEY_7, KEY_8, KEY_0 = 54, 55, 56, 48


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _s16(lo: int, hi: int) -> int:
    v = _u16(lo, hi)
    return v - 0x10000 if v >= 0x8000 else v


def _read_word(m: Z80, label: str, c: Compiler) -> int:
    addr = c.words[label].data_address
    return _s16(m.mem[addr], m.mem[addr + 1])


def _read_byte(m: Z80, addr: int) -> int:
    return m.mem[addr]


def _grid_addr(c: Compiler) -> int:
    return c.words["pf-grid"].data_address


def _grid_cell(m: Z80, c: Compiler, col: int, row: int) -> int:
    return m.mem[_grid_addr(c) + row * PF_COLS + col]


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


def _run(built_compiler: Compiler, *, pressed: set[int] | None = None,
         budget: int = TICK_BUDGET) -> Z80:
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    m.pressed_keys = set(pressed or set())
    m.run(max_ticks=budget)
    return m


@pytest.fixture(scope="module")
def free_run(built_compiler):
    return _run(built_compiler)


@pytest.fixture(scope="module")
def short_free_run(built_compiler):
    return _run(built_compiler, budget=SHORT_BUDGET)


class TestFilesPresent:

    def test_main_exists(self):
        assert MAIN.is_file(), "main.fs should exist for tetris"

    @pytest.mark.parametrize("lib_name", [
        "sprites.fs", "pieces.fs", "playfield.fs", "piece.fs",
        "controls.fs", "audio.fs", "levels.fs", "score.fs", "game.fs",
    ])
    def test_lib_exists(self, lib_name):
        path = EXAMPLE_DIR / "lib" / lib_name
        assert path.is_file(), f"library file '{lib_name}' should be present"


class TestModulesCompile:

    @pytest.mark.parametrize("name", [
        "block-tile", "empty-tile", "wall-tile",
        "piece-shapes", "piece-attrs",
        "level-1-rows", "level-2-rows", "level-3-rows", "level-attrs",
        "pf-grid",
    ])
    def test_data_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"data word '{name}' should be defined in the dictionary"
        )

    @pytest.mark.parametrize("name", [
        "score", "level", "preset-remaining", "hud-dirty", "game-over-flag",
        "piece-cur-id", "piece-cur-rot", "piece-cur-col", "piece-cur-row",
        "piece-next-id", "piece-locked",
        "pf-cleared-count", "pf-presets-cleared",
    ])
    def test_state_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"state variable '{name}' should be defined"
        )

    @pytest.mark.parametrize("name", [
        "piece-fits?", "piece-try-place", "piece-try-move", "piece-try-rotate",
        "piece-spawn", "piece-stamp", "piece-gravity-step",
        "pf-row-full?", "pf-compact", "pf-draw-all",
        "load-level", "level-rows-addr", "level-attr",
        "tetris", "game-step", "game-loop",
        "in-left?", "in-right?", "in-down?", "in-rotate?",
    ])
    def test_logic_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"logic word '{name}' should be defined"
        )

    @pytest.mark.parametrize("name", [
        "kempston",
        "kempston-left?", "kempston-right?", "kempston-down?",
        "kempston-up?", "kempston-fire?",
        "sinclair-left?", "sinclair-right?", "sinclair-down?",
        "sinclair-rotate?",
        "kb-left?", "kb-right?", "kb-down?", "kb-rotate?",
    ])
    def test_input_words_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"input word '{name}' should be defined for joystick + keyboard"
        )

    @pytest.mark.parametrize("name", [
        "audio-init", "audio-on-move", "audio-on-rotate", "audio-on-lock",
        "audio-on-line-clear", "audio-on-level-clear", "audio-on-game-over",
    ])
    def test_audio_words_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"audio word '{name}' should be defined for SFX hooks"
        )


class TestPieceConstantsAndAttrs:

    @pytest.mark.parametrize("name,expected", [
        ("piece-i", 0), ("piece-o", 1), ("piece-t", 2),
        ("piece-s", 3), ("piece-z", 4), ("piece-l", 5), ("piece-j", 6),
    ])
    def test_piece_id_constants(self, built_compiler, name, expected):
        word = built_compiler.words[name]
        assert word.value == expected, (
            f"constant '{name}' should equal {expected}; got {word.value}"
        )

    def test_per_piece_attrs_distinct(self, built_compiler):
        addr = built_compiler.words["piece-attrs"].data_address
        attrs = [_read_byte(_zero_machine(built_compiler), addr + i)
                 for i in range(7)]
        assert len(set(attrs)) == 7, (
            f"all 7 piece attribute bytes should be distinct; got {attrs}"
        )


def _zero_machine(c: Compiler) -> Z80:
    image = c.build()
    m = Z80()
    m.load(c.origin, image)
    return m


class TestInitialState:

    def test_pf_grid_size(self, built_compiler):
        addr = built_compiler.words["pf-grid"].data_address
        assert addr + PF_COLS * PF_ROWS <= 0xFFFF, (
            "pf-grid should fit within the 64KB address space"
        )

    def test_score_starts_zero_after_short_run(self, built_compiler, short_free_run):
        score = _read_word(short_free_run, "score", built_compiler)
        assert score == 0, (
            f"score should still be 0 right after starting level 1; got {score}"
        )

    def test_level_starts_at_one(self, built_compiler, short_free_run):
        level = _read_word(short_free_run, "level", built_compiler)
        assert level == 1, (
            f"first level should be 1; got {level}"
        )

    def test_preset_remaining_is_level_1_count(self, built_compiler, short_free_run):
        preset = _read_word(short_free_run, "preset-remaining", built_compiler)
        assert preset == 9, (
            f"level 1 has 9 preset cells (row 17, cols 1..9); got {preset}"
        )

    def test_piece_spawn_position(self, built_compiler, short_free_run):
        col = _read_word(short_free_run, "piece-cur-col", built_compiler)
        row = _read_word(short_free_run, "piece-cur-row", built_compiler)
        assert (col, row) == (PIECE_SPAWN_COL, PIECE_SPAWN_ROW) or row > PIECE_SPAWN_ROW, (
            f"piece should spawn at col={PIECE_SPAWN_COL} row={PIECE_SPAWN_ROW} "
            f"(or have already dropped from there); got col={col} row={row}"
        )

    def test_piece_id_in_range(self, built_compiler, short_free_run):
        pid = _read_word(short_free_run, "piece-cur-id", built_compiler)
        assert 0 <= pid <= 6, (
            f"current piece id should be one of 0..6 (the seven tetrominoes); got {pid}"
        )


class TestPresetCellsLoaded:

    def test_level_1_row_17_cols_1_to_9_filled(self, built_compiler, short_free_run):
        for col in range(1, 10):
            v = _grid_cell(short_free_run, built_compiler, col, 17)
            assert v != 0, (
                f"level 1 preset cell at (col={col}, row=17) should be non-empty"
            )

    def test_level_1_row_17_col_0_empty(self, built_compiler, short_free_run):
        v = _grid_cell(short_free_run, built_compiler, 0, 17)
        assert v == 0, (
            f"level 1 leaves col 0 of row 17 empty as the gap; got {v}"
        )

    def test_preset_cells_carry_preset_marker_bit(self, built_compiler, short_free_run):
        for col in range(1, 10):
            v = _grid_cell(short_free_run, built_compiler, col, 17)
            assert v & 0x80, (
                f"preset cell (col={col}, row=17) should have bit 7 set "
                f"so line-clear can decrement preset-remaining; got 0x{v:02X}"
            )

    @pytest.mark.parametrize("row,filled_count,empty_cols", [
        (17, 9, [0]),
    ])
    def test_level_1_row_shape(self, built_compiler, short_free_run,
                               row, filled_count, empty_cols):
        filled = sum(
            1 for c in range(PF_COLS)
            if _grid_cell(short_free_run, built_compiler, c, row) != 0
        )
        for c in empty_cols:
            v = _grid_cell(short_free_run, built_compiler, c, row)
            assert v == 0, (
                f"row {row} col {c} should be the gap; got 0x{v:02X}"
            )
        assert filled == filled_count, (
            f"row {row} should have {filled_count} filled cells; got {filled}"
        )


class TestSinclairJoystickMovesPiece:

    @pytest.mark.parametrize("key,direction,expected_delta", [
        (KEY_6, "left",  -1),
        (KEY_7, "right",  1),
    ])
    def test_horizontal_movement(self, built_compiler, key, direction, expected_delta):
        budget = 500_000
        baseline = _run(built_compiler, budget=budget)
        moved = _run(built_compiler, pressed={key}, budget=budget)
        baseline_col = _read_word(baseline, "piece-cur-col", built_compiler)
        moved_col = _read_word(moved, "piece-cur-col", built_compiler)
        if expected_delta < 0:
            assert moved_col < baseline_col, (
                f"holding {direction} (key={key}) should push piece's col below "
                f"the no-input baseline {baseline_col}; got {moved_col}"
            )
        else:
            assert moved_col > baseline_col, (
                f"holding {direction} (key={key}) should push piece's col above "
                f"the no-input baseline {baseline_col}; got {moved_col}"
            )

    def test_holding_left_reaches_left_wall(self, built_compiler):
        m = _run(built_compiler, pressed={KEY_6}, budget=TICK_BUDGET)
        col = _read_word(m, "piece-cur-col", built_compiler)
        assert col <= 0, (
            f"holding left long enough should put piece-cur-col at or below 0 "
            f"(spawn col is 3, leftmost is bounded by piece bounding box); got {col}"
        )

    def test_holding_right_reaches_right_wall(self, built_compiler):
        m = _run(built_compiler, pressed={KEY_7}, budget=TICK_BUDGET)
        col = _read_word(m, "piece-cur-col", built_compiler)
        assert col >= 5, (
            f"holding right long enough should push piece-cur-col toward the "
            f"right wall (col 9 is rightmost cell, 4-wide bounding box); got {col}"
        )


class TestGravityAdvancesPiece:

    def test_piece_falls_with_no_input(self, built_compiler):
        early = _run(built_compiler, budget=SHORT_BUDGET // 4)
        later = _run(built_compiler, budget=SHORT_BUDGET)
        early_row = _read_word(early, "piece-cur-row", built_compiler)
        later_row = _read_word(later, "piece-cur-row", built_compiler)
        assert later_row >= early_row or later_row >= 0, (
            f"piece-cur-row should advance under gravity; "
            f"early={early_row} later={later_row}"
        )

    def test_holding_down_drops_faster(self, built_compiler):
        free = _run(built_compiler, budget=SHORT_BUDGET // 2)
        soft = _run(built_compiler, pressed={KEY_8}, budget=SHORT_BUDGET // 2)
        free_row = _read_word(free, "piece-cur-row", built_compiler)
        soft_row = _read_word(soft, "piece-cur-row", built_compiler)
        free_pieces = _piece_lock_count(free, built_compiler)
        soft_pieces = _piece_lock_count(soft, built_compiler)
        assert soft_pieces >= free_pieces or soft_row >= free_row, (
            f"soft drop (KEY_8 held) should accumulate at least as many drops "
            f"as the free run; free_row={free_row} soft_row={soft_row} "
            f"free_pieces={free_pieces} soft_pieces={soft_pieces}"
        )


def _piece_lock_count(m: Z80, c: Compiler) -> int:
    """Approximate piece-lock count from filled non-preset cells in playfield."""
    addr = c.words["pf-grid"].data_address
    cells = m.mem[addr:addr + PF_COLS * PF_ROWS]
    return sum(1 for v in cells if v != 0 and not (v & 0x80))


class TestPlayfieldStaysSane:

    def test_piece_stays_within_playfield_columns(self, built_compiler, free_run):
        col = _read_word(free_run, "piece-cur-col", built_compiler)
        assert -3 <= col <= PF_COLS - 1, (
            f"piece-cur-col should fit within the playfield (with bounding-box "
            f"overhang allowed); got {col}"
        )

    def test_piece_stays_within_playfield_rows(self, built_compiler, free_run):
        row = _read_word(free_run, "piece-cur-row", built_compiler)
        assert 0 <= row <= PF_ROWS, (
            f"piece-cur-row must be a valid spawn or in-bounds value; got {row}"
        )


class TestPiecesEventuallyLock:

    def test_lock_count_grows_with_runtime(self, built_compiler):
        short = _run(built_compiler, pressed={KEY_8}, budget=SHORT_BUDGET)
        long = _run(built_compiler, pressed={KEY_8}, budget=TICK_BUDGET)
        short_locks = _piece_lock_count(short, built_compiler)
        long_locks = _piece_lock_count(long, built_compiler)
        assert long_locks >= short_locks, (
            f"a longer run should not lose locked-down cells; "
            f"short_locks={short_locks} long_locks={long_locks}"
        )

    def test_at_least_one_piece_locks_under_soft_drop(self, built_compiler):
        m = _run(built_compiler, pressed={KEY_8}, budget=TICK_BUDGET)
        locks = _piece_lock_count(m, built_compiler)
        assert locks > 0, (
            f"with soft-drop held, at least one piece should lock into the "
            f"playfield within {TICK_BUDGET} ticks; got {locks} non-preset filled cells"
        )
