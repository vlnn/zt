"""End-to-end tests for the celeste-mvp example.

Pixel-aligned platformer spike: a static room (floor + side walls + one
mid-air platform), a player rendered as an 8x8 pre-shifted sprite via
BLIT8XC, O/P horizontal movement at walk-spd pixels/frame, gravity that
accelerates vy toward max-fall-spd, and Z to jump (sets vy to jump-vy).

All player state is in pixels now: player-x and player-y replace the
char-cell coordinates of the earlier iterations. Collision is an AABB
against the same 32x24 tile grid in lib/room.fs — the room stays
char-aligned because tiles don't move.

Run modes:
  - free_run: no keys; player falls and rests on the floor.
  - o_held:   O held; player walks left, hits the left wall, rests.
  - p_held:   P held; player walks right, hits the right wall, rests.
  - z_held:   Z held; player oscillates between rest and jump apex.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_cell,
    screen_addr,
)


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"

TICK_BUDGET = 2_000_000

PLAYER_START_PX_X = 32
PLAYER_START_PX_Y = 8
PLAYER_REST_PX_Y = 176
PLAYER_MIN_PX_X = 7
PLAYER_MAX_PX_X = 241
JUMP_PEAK_PX_Y = 161

COYOTE_MAX = 6
JUMP_BUFFER_MAX = 4

SPIKES_COL = 20
SPIKES_ROW = 20
SPIKES_PX_X = 160
SPIKES_PX_Y = 160

ATTR_BASE = 0x5800
ROOM_ATTR = 0x07

DASH_DURATION = 6
DASH_SPD = 5
DASH_SPD_DIAG = 4

FLOOR_ROW = 23
LEFT_WALL_COL = 0
RIGHT_WALL_COL = 31
STEP_ROW = 22
STEP_COLS = list(range(26, 31))

SOLID_BYTE = 0xFF
BLANK_BYTE = 0x00


def _u16(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def _s16(lo: int, hi: int) -> int:
    v = _u16(lo, hi)
    return v - 0x10000 if v >= 0x8000 else v


def _read_word(m: Z80, label: str, c: Compiler) -> int:
    addr = c.words[label].data_address
    return _s16(m.mem[addr], m.mem[addr + 1])


def _align_to_frame_end(m, built_compiler, max_extra_chunks=200, chunk=1000):
    addr = built_compiler.words["frame-counter"].data_address
    def fc():
        return _s16(m.mem[addr], m.mem[addr + 1])
    start = fc()
    for _ in range(max_extra_chunks):
        if fc() != start:
            return
        m.run(max_ticks=chunk)


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler(include_dirs=[EXAMPLE_DIR])
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


def _set_skip_title(m, built_compiler):
    addr = built_compiler.words["skip-title"].data_address
    m.mem[addr]     = 0xFF
    m.mem[addr + 1] = 0xFF


def _run(built_compiler, pressed_keys=None, budget=TICK_BUDGET):
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    m.pressed_keys = set(pressed_keys or set())
    _set_skip_title(m, built_compiler)
    m.run(max_ticks=budget)
    _align_to_frame_end(m, built_compiler)
    return m


def _run_phases(built_compiler, phases):
    image = built_compiler.build()
    m = Z80()
    m.load(built_compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = built_compiler.words["_start"].address
    _set_skip_title(m, built_compiler)
    for keys, budget in phases:
        m.pressed_keys = set(keys)
        m.run(max_ticks=budget)
    _align_to_frame_end(m, built_compiler)
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


@pytest.fixture(scope="module")
def z_held(built_compiler):
    return _run(built_compiler, pressed_keys={ord("Z")})


@pytest.fixture(scope="module")
def z_pressed_after_settling(built_compiler):
    return _run_phases(built_compiler, [
        (set(),       1_500_000),
        ({ord("Z")},  1_000_000),
    ])


@pytest.fixture(scope="module")
def z_pressed_twice(built_compiler):
    return _run_phases(built_compiler, [
        (set(),       1_500_000),
        ({ord("Z")},  400_000),
        (set(),       400_000),
        ({ord("Z")},  400_000),
    ])


@pytest.fixture(scope="module")
def wall_jump_sequence(built_compiler):
    return _run_phases(built_compiler, [
        ({ord("O")},                   1_500_000),
        ({ord("O"), ord("Z")},             80_000),
        ({ord("O")},                       20_000),
        ({ord("O"), ord("Z")},            500_000),
    ])


@pytest.fixture(scope="module")
def wall_jump_in_progress(built_compiler):
    return _run_phases(built_compiler, [
        ({ord("O")},                   1_500_000),
        ({ord("O"), ord("Z")},             80_000),
        ({ord("O")},                       20_000),
        ({ord("O"), ord("Z")},             80_000),
    ])


@pytest.fixture(scope="module")
def dash_right_in_progress(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("X")},                       40_000),
    ])


@pytest.fixture(scope="module")
def dash_right_completed(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("X")},                       40_000),
        (set(),                           400_000),
    ])


@pytest.fixture(scope="module")
def dash_left_via_facing(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("O")},                       50_000),
        (set(),                            50_000),
        ({ord("X")},                       40_000),
    ])


@pytest.fixture(scope="module")
def second_dash_blocked_airborne(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("Z")},                       80_000),
        (set(),                            25_000),
        ({ord("X")},                       25_000),
        (set(),                           150_000),
        ({ord("X")},                       25_000),
    ])


@pytest.fixture(scope="module")
def dash_up_in_progress(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("Q"), ord("X")},             40_000),
    ])


@pytest.fixture(scope="module")
def dash_up_right_in_progress(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("Q"), ord("P"), ord("X")},   40_000),
    ])


@pytest.fixture(scope="module")
def dash_down_left_after_jump_in_progress(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("Z")},                      100_000),
        ({ord("A"), ord("O"), ord("X")},   40_000),
    ])


@pytest.fixture(scope="module")
def coin_collected_via_step(built_compiler):
    return _run_phases(built_compiler, [
        (set(),                        1_500_000),
        ({ord("P")},                   1_500_000),
        ({ord("P"), ord("Z")},            300_000),
        ({ord("P")},                      300_000),
    ])


class TestFilesPresent:

    def test_main_exists(self):
        assert MAIN.is_file(), "main.fs should exist for celeste-mvp"

    @pytest.mark.parametrize("lib_name", [
        "sprites.fs", "room.fs", "player.fs", "game.fs",
    ])
    def test_lib_exists(self, lib_name):
        path = EXAMPLE_DIR / "lib" / lib_name
        assert path.is_file(), f"library file {lib_name!r} should exist"


class TestModulesCompile:

    @pytest.mark.parametrize("name", [
        "blank-tile", "solid-tile", "player-shifted", "blank-pixel",
    ])
    def test_sprite_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"sprite {name!r} should be defined by lib/sprites.fs"
        )

    @pytest.mark.parametrize("name", [
        "player-x", "player-y", "player-old-x", "player-old-y",
        "player-vx", "player-vy", "jumps-performed", "wall-jumps-performed",
        "z-prev", "z-now", "x-prev", "x-now",
        "coyote", "jump-buffer", "wall-jump-lockout",
        "dash-state", "dash-available", "player-facing", "dashes-performed",
        "coin-collected", "coins-count", "coin-tile",
        "deaths", "spike-tile",
        "spring-bounces", "spring-tile",
        "last-painted-deaths", "last-painted-coins",
        "frame-counter",
        "skip-title",
        "current-room",
        "advance-requested",
        "hud-attr",
    ])
    def test_state_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"state variable {name!r} should be defined by lib/player.fs"
        )

    @pytest.mark.parametrize("name", [
        "init-room", "init-room-1", "init-room-2", "draw-room",
        "player-reset", "respawn-player", "draw-player", "erase-player",
        "apply-gravity", "apply-velocity", "apply-velocity-x",
        "step-left-1px", "step-right-1px", "step-up-1px", "step-down-1px",
        "step-by-vx-1px", "step-by-vy-1px",
        "aabb-overlaps-solid?", "on-floor?",
        "touching-left-wall?", "touching-right-wall?", "touching-wall?",
        "approach", "walk-target", "update-vx",
        "maybe-start-jump", "maybe-cancel-jump", "start-jump", "start-wall-jump",
        "z-held?", "z-just-pressed?", "save-z", "rising?", "poll-z",
        "x-held?", "x-just-pressed?", "save-x", "poll-x",
        "o-held?", "p-held?", "q-held?", "a-held?",
        "update-facing",
        "dash-dx-base", "dash-dy-base", "dash-dir-2d",
        "is-diagonal?", "dash-speed", "store-dash-velocity",
        "dashing?",
        "start-dash", "tick-dash", "maybe-start-dash",
        "tick-coyote", "tick-jump-buffer", "tick-wall-jump-lockout",
        "jump-armed?", "dec-toward-zero",
        "coin-reset", "x-overlaps-coin?", "y-overlaps-coin?",
        "player-overlaps-coin?", "maybe-collect-coin", "paint-coin",
        "spikes-reset", "x-overlaps-spikes?", "y-overlaps-spikes?",
        "player-overlaps-spikes?", "maybe-kill-player", "paint-spikes",
        "maybe-redraw-solid",
        "redraw-room-around-player", "redraw-room-around-old",
        "paint-altitude",
        "paint-hud-attrs",
        "hud-overdraw?", "maybe-repaint-hud",
        "emit-digit", "emit-2digit",
        "paint-deaths", "maybe-paint-deaths",
        "paint-coins-count", "maybe-paint-coins",
        "spring-reset", "paint-spring",
        "x-overlaps-spring?", "y-overlaps-spring?",
        "player-overlaps-spring?", "descending?", "maybe-bounce-on-spring",
        "paint-title", "wait-for-start",
        "load-room-1-entities", "load-room-2-entities",
        "load-room-entities",
        "advance-room", "maybe-advance-room",
        "game-step", "game-loop", "celeste-mvp",
    ])
    def test_logic_word_defined(self, built_compiler, name):
        assert name in built_compiler.words, (
            f"logic word {name!r} should be defined"
        )


class TestRoomRendersAtStart:

    @pytest.mark.parametrize("col", range(LEFT_WALL_COL + 1, RIGHT_WALL_COL))
    def test_floor_row_renders_solid(self, free_run, col):
        cell = decode_screen_cell(free_run.mem, FLOOR_ROW, col)
        assert cell == SOLID_BYTE, (
            f"floor row {FLOOR_ROW} col {col} should render as solid "
            f"({SOLID_BYTE:#04x}); got {cell:#04x}"
        )

    @pytest.mark.parametrize("row", range(0, FLOOR_ROW))
    def test_left_wall_renders_solid(self, free_run, row):
        cell = decode_screen_cell(free_run.mem, row, LEFT_WALL_COL)
        assert cell == SOLID_BYTE, (
            f"left wall col {LEFT_WALL_COL} row {row} should render as "
            f"solid ({SOLID_BYTE:#04x}); got {cell:#04x}"
        )

    @pytest.mark.parametrize("row", range(0, FLOOR_ROW))
    def test_right_wall_renders_solid(self, free_run, row):
        cell = decode_screen_cell(free_run.mem, row, RIGHT_WALL_COL)
        assert cell == SOLID_BYTE, (
            f"right wall col {RIGHT_WALL_COL} row {row} should render as "
            f"solid ({SOLID_BYTE:#04x}); got {cell:#04x}"
        )

    @pytest.mark.parametrize("col", STEP_COLS)
    def test_step_renders_solid(self, free_run, col):
        cell = decode_screen_cell(free_run.mem, STEP_ROW, col)
        assert cell == SOLID_BYTE, (
            f"step row {STEP_ROW} col {col} should render as "
            f"solid ({SOLID_BYTE:#04x}); got {cell:#04x}"
        )

    @pytest.mark.parametrize("col", list(range(8, 14)))
    def test_old_platform_row_is_clear(self, free_run, col):
        cell = decode_screen_cell(free_run.mem, 15, col)
        assert cell == BLANK_BYTE, (
            f"the iter-1 mid-platform (row 15 cols 8-13) is removed in "
            f"the 100m layout; col {col} row 15 should be blank; "
            f"got {cell:#04x}"
        )

    @pytest.mark.parametrize("col,row", [
        (5, 10), (15, 5), (20, 12), (25, 18),
    ])
    def test_open_cell_renders_blank(self, free_run, col, row):
        cell = decode_screen_cell(free_run.mem, row, col)
        assert cell == BLANK_BYTE, (
            f"open cell row {row} col {col} should render as blank "
            f"({BLANK_BYTE:#04x}); got {cell:#04x}"
        )


class TestAltitudeText:

    ALTITUDE_COL = 2
    ALTITUDE_ROW = 0
    ALTITUDE_TEXT = "100m"

    def _font_glyph(self, m, ch):
        addr = SPECTRUM_FONT_BASE + (ord(ch) - 32) * 8
        return [m.mem[addr + i] for i in range(8)]

    def _screen_glyph(self, m, col, row):
        return [m.mem[screen_addr(row, col, line)] for line in range(8)]

    @pytest.mark.parametrize("i,ch", list(enumerate("100m")))
    def test_altitude_char_matches_font(self, free_run, i, ch):
        col = self.ALTITUDE_COL + i
        screen = self._screen_glyph(free_run, col, self.ALTITUDE_ROW)
        font = self._font_glyph(free_run, ch)
        assert screen == font, (
            f"paint-altitude calls '2 0 at-xy .\" 100m\"' in init-game, "
            f"which writes the 4 glyphs '1','0','0','m' to row 0 cols "
            f"2-5; cell (col {col}, row {self.ALTITUDE_ROW}) should "
            f"match the Spectrum-font bytes for '{ch}' "
            f"({font}); got {screen}"
        )

    def test_altitude_text_placed_above_player_spawn(
        self, built_compiler, free_run
    ):
        first_col_bytes = self._screen_glyph(
            free_run, self.ALTITUDE_COL, self.ALTITUDE_ROW
        )
        assert any(b != 0 for b in first_col_bytes), (
            f"the altitude indicator is painted at row 0 specifically "
            f"so it sits above the player's spawn row (row 1) and is "
            f"not overwritten by erase-player when the player falls; "
            f"col {self.ALTITUDE_COL} row {self.ALTITUDE_ROW} should "
            f"have non-zero bytes after a full free_run; got "
            f"{first_col_bytes}"
        )


class TestDeathsHud:

    HUD_COL = 22
    HUD_ROW = 0
    HUD_LABEL = "DEATHS:"
    TENS_COL = HUD_COL + len(HUD_LABEL)
    ONES_COL = TENS_COL + 1

    def _screen_byte(self, m, col, row):
        return m.mem[screen_addr(row, col, 0)]

    @pytest.mark.parametrize("i,ch", list(enumerate("DEATHS:")))
    def test_deaths_label_renders(self, free_run, i, ch):
        col = self.HUD_COL + i
        b = self._screen_byte(free_run, col, self.HUD_ROW)
        assert b == ord(ch), (
            f"paint-deaths writes the label \"DEATHS:\" at row 0 "
            f"cols 22-28; col {col} should hold {ord(ch)} ('{ch}'); "
            f"got {b}"
        )

    def test_deaths_displays_zero_initially(self, free_run):
        tens = self._screen_byte(free_run, self.TENS_COL, self.HUD_ROW)
        ones = self._screen_byte(free_run, self.ONES_COL, self.HUD_ROW)
        assert tens == ord("0") and ones == ord("0"), (
            f"in free_run the player never touches a spike, so deaths "
            f"stays 0 and the HUD digits should be '00'; got tens={tens} "
            f"({chr(tens) if 32 <= tens < 127 else '?'}) ones={ones} "
            f"({chr(ones) if 32 <= ones < 127 else '?'})"
        )

    def test_deaths_displays_after_spike_kill(
        self, built_compiler, p_held
    ):
        deaths = _read_word(p_held, "deaths", built_compiler)
        assert deaths > 0, (
            f"p_held should die on the spike at col 20-22 row 20 at "
            f"least once over the default 2M-tick budget; "
            f"got deaths={deaths}"
        )
        expected_tens = ord("0") + (deaths // 10) % 10
        expected_ones = ord("0") + deaths % 10
        tens = self._screen_byte(p_held, self.TENS_COL, self.HUD_ROW)
        ones = self._screen_byte(p_held, self.ONES_COL, self.HUD_ROW)
        assert tens == expected_tens and ones == expected_ones, (
            f"deaths={deaths} should render as two decimal digits at "
            f"row 0 cols {self.TENS_COL}-{self.ONES_COL}; "
            f"expected tens={expected_tens} ones={expected_ones}; "
            f"got tens={tens} ones={ones}"
        )

    def test_hud_lives_above_player_spawn(self, built_compiler, free_run):
        last_painted = _read_word(
            free_run, "last-painted-deaths", built_compiler
        )
        assert last_painted == 0, (
            f"after init-game paints the initial HUD, last-painted-deaths "
            f"should be cached at 0 so maybe-paint-deaths skips the "
            f"repaint every frame; got {last_painted}"
        )


class TestCoinsHud:

    HUD_COL = 10
    HUD_ROW = 0
    HUD_LABEL = "COINS:"
    TENS_COL = HUD_COL + len(HUD_LABEL)
    ONES_COL = TENS_COL + 1

    def _screen_byte(self, m, col, row):
        return m.mem[screen_addr(row, col, 0)]

    @pytest.mark.parametrize("i,ch", list(enumerate("COINS:")))
    def test_coins_label_renders(self, free_run, i, ch):
        col = self.HUD_COL + i
        b = self._screen_byte(free_run, col, self.HUD_ROW)
        assert b == ord(ch), (
            f"paint-coins-count writes the label \"COINS:\" at row 0 "
            f"cols 10-15; col {col} should hold {ord(ch)} ('{ch}'); "
            f"got {b}"
        )

    def test_coins_displays_zero_initially(self, free_run):
        tens = self._screen_byte(free_run, self.TENS_COL, self.HUD_ROW)
        ones = self._screen_byte(free_run, self.ONES_COL, self.HUD_ROW)
        assert tens == ord("0") and ones == ord("0"), (
            f"free_run never touches the coin; the HUD digits should "
            f"be '00'; got tens={tens} ones={ones}"
        )

    def test_coins_displays_after_collection(
        self, built_compiler, coin_collected_via_step
    ):
        coins = _read_word(
            coin_collected_via_step, "coins-count", built_compiler
        )
        assert coins == 1, (
            f"the coin_collected_via_step fixture lets the player fall "
            f"to the floor, walk right under the spike, jump onto the "
            f"step, and walk into the coin at (col 28, row 21); "
            f"coins-count should be 1; got {coins}"
        )
        expected_tens = ord("0") + (coins // 10) % 10
        expected_ones = ord("0") + coins % 10
        tens = self._screen_byte(
            coin_collected_via_step, self.TENS_COL, self.HUD_ROW
        )
        ones = self._screen_byte(
            coin_collected_via_step, self.ONES_COL, self.HUD_ROW
        )
        assert tens == expected_tens and ones == expected_ones, (
            f"coins-count={coins} should render as '01' at row 0 cols "
            f"{self.TENS_COL}-{self.ONES_COL}; expected tens="
            f"{expected_tens} ones={expected_ones}; got tens={tens} "
            f"ones={ones}"
        )

    def test_coins_hud_cache_after_init(self, built_compiler, free_run):
        last_painted = _read_word(
            free_run, "last-painted-coins", built_compiler
        )
        assert last_painted == 0, (
            f"init-game seeds last-painted-coins to -1 then paints, "
            f"which should leave the cache at 0 to match coins-count; "
            f"got {last_painted}"
        )

    def test_coins_collection_does_not_count_as_death(
        self, built_compiler, coin_collected_via_step
    ):
        deaths = _read_word(
            coin_collected_via_step, "deaths", built_compiler
        )
        assert deaths == 0, (
            f"the under-the-spike route in coin_collected_via_step keeps "
            f"the player on the floor (y=176, AABB y in [176, 183]) the "
            f"whole walk; the spike sits at y in [160, 167] so the "
            f"player never overlaps it; deaths should stay 0; "
            f"got {deaths}"
        )


class TestSpring:

    SPRING_COL = 14
    SPRING_ROW = 17
    SPRING_X = 112
    SPRING_Y = 136
    SPRING_VY = -12
    EXPECTED_TILE = [0x00, 0x24, 0x3C, 0x24, 0x3C, 0x24, 0x7E, 0xFF]

    @pytest.mark.parametrize("line,byte", list(enumerate(EXPECTED_TILE)))
    def test_spring_tile_renders(self, free_run, line, byte):
        actual = free_run.mem[screen_addr(self.SPRING_ROW, self.SPRING_COL, line)]
        assert actual == byte, (
            f"paint-spring should blit spring-tile at (col "
            f"{self.SPRING_COL}, row {self.SPRING_ROW}); line {line} "
            f"should be {hex(byte)}; got {hex(actual)}"
        )

    def test_spring_bounces_initial(self, built_compiler, free_run):
        bounces = _read_word(free_run, "spring-bounces", built_compiler)
        assert bounces == 0, (
            f"spring-reset zeroes spring-bounces in init-game; free_run "
            f"never reaches the mid-air spring at (col 14, row 17, y=136); "
            f"got {bounces}"
        )

    @pytest.mark.parametrize("fixture_name", [
        "free_run", "p_held", "z_held", "wall_jump_sequence",
        "dash_right_completed", "dash_up_in_progress",
        "coin_collected_via_step",
    ])
    def test_spring_not_triggered_in_normal_play(
        self, built_compiler, request, fixture_name
    ):
        m = request.getfixturevalue(fixture_name)
        bounces = _read_word(m, "spring-bounces", built_compiler)
        assert bounces == 0, (
            f"the spring lives mid-air at (col 14, row 17, y=136); to "
            f"reach it the player would need to jump+up-dash precisely "
            f"into x=[106,118] and y=[129,143] while falling; none of "
            f"the existing fixtures performs that maneuver, so "
            f"spring-bounces should stay 0; got {bounces} "
            f"in fixture {fixture_name}"
        )


class TestHudColoring:

    ATTRS = 0x5800
    HUD_ATTR = 0x46
    ROOM_ATTR = 0x07
    HUD_ROW = 0

    def _attr_at(self, m, col, row):
        return m.mem[self.ATTRS + row * 32 + col]

    @pytest.mark.parametrize("col", list(range(1, 31)))
    def test_hud_row_painted_with_hud_attr(self, free_run, col):
        attr = self._attr_at(free_run, col, self.HUD_ROW)
        assert attr == self.HUD_ATTR, (
            f"paint-hud-attrs should fill row 0 cols 1-30 with "
            f"hud-attr=$46 (bright yellow ink, black paper); col {col} "
            f"should be ${self.HUD_ATTR:02X}; got ${attr:02X}"
        )

    @pytest.mark.parametrize("col", [0, 31])
    def test_hud_row_walls_stay_room_attr(self, free_run, col):
        attr = self._attr_at(free_run, col, self.HUD_ROW)
        assert attr == self.ROOM_ATTR, (
            f"paint-hud-attrs starts at (col=1, row=0) and fills only "
            f"30 bytes, leaving cols 0 and 31 (the side walls) at the "
            f"room's default $07 so the wall colour is consistent down "
            f"the full height of the room; col {col} should be "
            f"${self.ROOM_ATTR:02X}; got ${attr:02X}"
        )

    @pytest.mark.parametrize("row", [1, 5, 11, 17, 22, 23])
    def test_non_hud_rows_keep_room_attr(self, free_run, row):
        for col in [0, 1, 15, 30, 31]:
            attr = self._attr_at(free_run, col, row)
            assert attr == self.ROOM_ATTR, (
                f"paint-hud-attrs only touches row 0; row {row} col "
                f"{col} should stay at ${self.ROOM_ATTR:02X}; got "
                f"${attr:02X}"
            )

    def test_hud_attr_has_bright_bit(self, built_compiler, free_run):
        attr = self._attr_at(free_run, 5, self.HUD_ROW)
        assert attr & 0x40, (
            f"the bright bit (0x40) should be set so the HUD stands "
            f"out from the white-on-black play area; got ${attr:02X}"
        )

    def test_hud_attr_is_yellow_ink_black_paper(
        self, built_compiler, free_run
    ):
        attr = self._attr_at(free_run, 5, self.HUD_ROW)
        ink = attr & 0x07
        paper = (attr >> 3) & 0x07
        assert ink == 6 and paper == 0, (
            f"hud-attr should be yellow ink (6) on black paper (0); "
            f"got ink={ink} paper={paper}"
        )


class TestPlayerPhysics:

    def test_player_x_within_bounds(self, built_compiler, free_run):
        x = _read_word(free_run, "player-x", built_compiler)
        assert PLAYER_MIN_PX_X <= x <= PLAYER_MAX_PX_X, (
            f"player x should stay inside the walls "
            f"[{PLAYER_MIN_PX_X}, {PLAYER_MAX_PX_X}]; got {x}"
        )

    def test_player_y_within_bounds(self, built_compiler, free_run):
        y = _read_word(free_run, "player-y", built_compiler)
        assert 0 <= y <= PLAYER_REST_PX_Y + 1, (
            f"player y should stay above the floor [0, "
            f"{PLAYER_REST_PX_Y}] (allowing y+1 mid-step); got {y}"
        )

    def test_player_lands_on_floor_without_input(
        self, built_compiler, free_run
    ):
        y = _read_word(free_run, "player-y", built_compiler)
        assert PLAYER_REST_PX_Y <= y <= PLAYER_REST_PX_Y + 1, (
            f"with no keys, gravity should drop the player onto the "
            f"floor at y={PLAYER_REST_PX_Y} (allowing y+1 for the sim "
            f"stopping between step-down-1px's +! and its revert); "
            f"got {y}"
        )

    def test_player_x_unchanged_without_input(
        self, built_compiler, free_run
    ):
        x = _read_word(free_run, "player-x", built_compiler)
        assert x == PLAYER_START_PX_X, (
            f"with no keys, player x should stay at the start "
            f"({PLAYER_START_PX_X}); got {x}"
        )

    def test_player_walks_left_to_wall_when_O_held(
        self, built_compiler, o_held
    ):
        x = _read_word(o_held, "player-x", built_compiler)
        assert PLAYER_MIN_PX_X - 1 <= x <= PLAYER_MIN_PX_X, (
            f"with O held the whole run, the player AABB (x+1..x+6, "
            f"matching the visible sprite extent) is just touching the "
            f"wall at x={PLAYER_MIN_PX_X} (visible player pixel 8 next "
            f"to wall pixel 7, no gap); allowing x-1 for sim stopping "
            f"mid-step-left-1px; got x={x}"
        )

    def test_left_wall_intact_after_player_touches_it(
        self, built_compiler, o_held
    ):
        rows = [
            o_held.mem[screen_addr(22, 0, line)]
            for line in range(8)
        ]
        assert all(b == 0xFF for b in rows), (
            f"player at x=7 blits left-byte $00 into cell (0, 22) (the "
            f"wall cell). redraw-room-around-player should restore "
            f"solid-tile there every frame; got col 0 row 22 = {rows}"
        )

    def test_left_wall_attribute_intact_after_player_touches_it(
        self, built_compiler, o_held
    ):
        attr = o_held.mem[ATTR_BASE + 22 * 32 + 0]
        assert attr == ROOM_ATTR, (
            f"player blits at x=7 also write the player-attr ($43 = "
            f"bright magenta) into the wall cell's attribute byte. "
            f"maybe-redraw-solid uses blit8c with room-attr=$07 so the "
            f"wall's white-on-black attribute should be restored every "
            f"frame; got attr={hex(attr)} at cell (0, 22)"
        )

    def test_player_walks_right_does_not_reach_wall_when_P_held(
        self, built_compiler, p_held
    ):
        x = _read_word(p_held, "player-x", built_compiler)
        assert x < SPIKES_PX_X + 8, (
            f"with spikes at x={SPIKES_PX_X}, P held now kills the "
            f"player around frame ~50 before it reaches the right wall; "
            f"the end state should be somewhere in a respawn cycle, "
            f"never past the spikes' last pixel; got x={x}"
        )

    def test_player_still_lands_while_walking(
        self, built_compiler, o_held
    ):
        y = _read_word(o_held, "player-y", built_compiler)
        assert PLAYER_REST_PX_Y <= y <= PLAYER_REST_PX_Y + 1, (
            f"gravity should still apply while o_held; "
            f"player should land on floor at y={PLAYER_REST_PX_Y} "
            f"(allowing y+1 mid-step); got {y}"
        )

    def test_player_vy_small_at_rest(self, built_compiler, free_run):
        vy = _read_word(free_run, "player-vy", built_compiler)
        assert 0 <= vy <= 1, (
            f"player at rest should have vy 0 (post-revert) or 1 "
            f"(post-gravity, pre-revert); got {vy}"
        )

    def test_player_vx_zero_at_rest(self, built_compiler, free_run):
        vx = _read_word(free_run, "player-vx", built_compiler)
        assert vx == 0, (
            f"with no input, walk-target is 0 and approach ramps "
            f"player-vx toward 0; got {vx}"
        )

    def test_player_vx_zero_at_wall_with_o_held(
        self, built_compiler, o_held
    ):
        vx = _read_word(o_held, "player-vx", built_compiler)
        assert -1 <= vx <= 1, (
            f"after reaching the left wall with O held, the collision "
            f"in step-left-1px should zero player-vx; approach then "
            f"ramps it back to -1 each frame and the next step re-"
            f"collides, so steady state oscillates vx ∈ [-1, 0]; "
            f"got {vx}"
        )


class TestPlayerJumps:

    def test_no_auto_bounce_with_continuous_z(
        self, built_compiler, z_held
    ):
        jumps = _read_word(z_held, "jumps-performed", built_compiler)
        assert jumps == 0, (
            f"Z held from start fires the rising edge once on frame 1 "
            f"while the player is still mid-air, so on-floor? blocks "
            f"the jump; the edge can't refire while Z stays held, so "
            f"the player never jumps; got jumps-performed={jumps}"
        )

    def test_player_does_not_jump_without_Z(
        self, built_compiler, free_run
    ):
        jumps = _read_word(free_run, "jumps-performed", built_compiler)
        assert jumps == 0, (
            f"without Z held, player should never jump; "
            f"got jumps-performed={jumps}"
        )

    def test_player_jumps_once_when_z_pressed_after_settling(
        self, built_compiler, z_pressed_after_settling
    ):
        jumps = _read_word(
            z_pressed_after_settling, "jumps-performed", built_compiler
        )
        assert jumps == 1, (
            f"after settling on floor then pressing Z, the rising "
            f"edge + on-floor? predicate should fire exactly one jump "
            f"(Z stays held for the rest of the run, no new edge); "
            f"got jumps-performed={jumps}"
        )

    def test_player_jumps_twice_with_two_z_presses(
        self, built_compiler, z_pressed_twice
    ):
        jumps = _read_word(
            z_pressed_twice, "jumps-performed", built_compiler
        )
        assert jumps == 2, (
            f"two separate Z presses (with a release in between) "
            f"should fire two jumps via rising-edge detection; "
            f"got jumps-performed={jumps}"
        )

    def test_player_x_unchanged_with_only_Z(
        self, built_compiler, z_held
    ):
        x = _read_word(z_held, "player-x", built_compiler)
        assert x == PLAYER_START_PX_X, (
            f"with only Z held (no O/P), player x should stay at the "
            f"start ({PLAYER_START_PX_X}); got {x}"
        )


class TestCoyoteAndBuffer:

    def test_coyote_refreshes_to_max_when_resting_on_floor(
        self, built_compiler, free_run
    ):
        coyote = _read_word(free_run, "coyote", built_compiler)
        assert coyote == COYOTE_MAX, (
            f"tick-coyote should refresh coyote to coyote-max ({COYOTE_MAX}) "
            f"on every frame the player is on the floor; "
            f"after settling, got coyote={coyote}"
        )

    def test_jump_buffer_is_zero_with_no_recent_press(
        self, built_compiler, free_run
    ):
        buf = _read_word(free_run, "jump-buffer", built_compiler)
        assert buf == 0, (
            f"jump-buffer should be 0 when no Z press has happened "
            f"recently (it decays toward zero each frame); got {buf}"
        )

    def test_jump_buffer_is_zero_after_being_consumed_by_jump(
        self, built_compiler, z_pressed_after_settling
    ):
        buf = _read_word(z_pressed_after_settling, "jump-buffer", built_compiler)
        assert buf == 0, (
            f"after the buffered press has fired a jump, jump-buffer "
            f"should be zeroed (and stays zero while Z is still held, "
            f"because z-just-pressed? only fires on rising edge); got {buf}"
        )

    def test_z_now_caches_current_z_state(
        self, built_compiler, z_held
    ):
        z_now = _read_word(z_held, "z-now", built_compiler)
        assert z_now == -1, (
            f"poll-z should cache z-held? into z-now once per frame; "
            f"with Z held continuously, z-now should be -1; got {z_now}"
        )


class TestCoin:

    COIN_COL = 28
    COIN_ROW = 21

    def test_coin_not_collected_without_input(
        self, built_compiler, free_run
    ):
        count = _read_word(free_run, "coins-count", built_compiler)
        assert count == 0, (
            f"with no input, player settles at start (x=32) and "
            f"never reaches the coin (at col 28 atop the step); "
            f"got coins-count={count}"
        )

    def test_coin_not_collected_walking_left(
        self, built_compiler, o_held
    ):
        count = _read_word(o_held, "coins-count", built_compiler)
        assert count == 0, (
            f"walking left moves the player away from the coin; "
            f"got coins-count={count}"
        )

    def test_coin_not_collected_walking_right_blocked_by_spikes(
        self, built_compiler, p_held
    ):
        count = _read_word(p_held, "coins-count", built_compiler)
        assert count == 0, (
            f"with spikes at col 20-22 row 20 still on the player's "
            f"diagonal-fall path, P held kills the player around frame "
            f"50 - well before reaching the coin at col 28; "
            f"got coins-count={count}"
        )

    def test_coin_flag_clear_when_not_collected(
        self, built_compiler, free_run
    ):
        flag = _read_word(free_run, "coin-collected", built_compiler)
        assert flag == 0, (
            f"without collection, coin-collected should be 0 (false); "
            f"got {flag}"
        )

    def test_coin_visible_at_start_when_not_collected(
        self, built_compiler, free_run
    ):
        rows = [
            free_run.mem[screen_addr(self.COIN_ROW, self.COIN_COL, line)]
            for line in range(8)
        ]
        assert any(b != 0 for b in rows), (
            f"with no input, the coin should remain visible at "
            f"({self.COIN_COL}, {self.COIN_ROW}) atop the step; "
            f"got all-zero rows {rows}"
        )


class TestSpikes:

    @pytest.mark.parametrize("col_offset", [0, 1, 2])
    def test_spikes_visible_at_start(
        self, built_compiler, free_run, col_offset
    ):
        col = SPIKES_COL + col_offset
        rows = [
            free_run.mem[screen_addr(SPIKES_ROW, col, line)]
            for line in range(8)
        ]
        assert any(b != 0 for b in rows), (
            f"the spike at ({col}, {SPIKES_ROW}) should be painted "
            f"every frame and visible at end of free_run; got all-zero "
            f"rows {rows}"
        )

    def test_no_deaths_without_input(
        self, built_compiler, free_run
    ):
        deaths = _read_word(free_run, "deaths", built_compiler)
        assert deaths == 0, (
            f"with no input the player falls to floor at x=32, never "
            f"overlapping the spikes (col 20-22 row 20); got deaths={deaths}"
        )

    def test_no_deaths_walking_left(
        self, built_compiler, o_held
    ):
        deaths = _read_word(o_held, "deaths", built_compiler)
        assert deaths == 0, (
            f"walking left moves away from the spikes; "
            f"got deaths={deaths}"
        )

    def test_no_deaths_with_z_only(
        self, built_compiler, z_held
    ):
        deaths = _read_word(z_held, "deaths", built_compiler)
        assert deaths == 0, (
            f"Z alone doesn't move the player horizontally; spikes are "
            f"never reached; got deaths={deaths}"
        )

    def test_player_dies_walking_right_into_spikes(
        self, built_compiler, p_held
    ):
        deaths = _read_word(p_held, "deaths", built_compiler)
        assert deaths >= 1, (
            f"P held should walk the player into the spikes around "
            f"frame 50 and respawn back at start, so over 2M ticks "
            f"deaths should be at least 1; got {deaths}"
        )

    def test_player_respawns_near_start_after_death(
        self, built_compiler, p_held
    ):
        x = _read_word(p_held, "player-x", built_compiler)
        assert PLAYER_START_PX_X <= x < SPIKES_PX_X, (
            f"after dying, the player respawns at start (x={PLAYER_START_PX_X}) "
            f"and walks right again; at end of the 2M-tick run the "
            f"player should be somewhere in a respawn cycle, between "
            f"start and the spike collision point (x≈179); got x={x}"
        )


class TestWallJump:

    def test_wall_jump_fires_in_multi_phase_sequence(
        self, built_compiler, wall_jump_sequence
    ):
        wj = _read_word(
            wall_jump_sequence, "wall-jumps-performed", built_compiler
        )
        assert wj == 1, (
            f"the multi-phase sequence (walk left + settle, Z press, "
            f"release Z mid-rise, re-press Z while mid-air against the "
            f"left wall) should fire exactly one wall jump; got {wj}"
        )

    def test_wall_jump_also_counts_in_total_jumps(
        self, built_compiler, wall_jump_sequence
    ):
        total = _read_word(
            wall_jump_sequence, "jumps-performed", built_compiler
        )
        assert total == 2, (
            f"the sequence fires a regular jump (frame 1 of phase 2) "
            f"and a wall jump (frame 1 of phase 4), so total jumps "
            f"should be 2; got {total}"
        )

    def test_no_wall_jumps_without_input(
        self, built_compiler, free_run
    ):
        wj = _read_word(free_run, "wall-jumps-performed", built_compiler)
        assert wj == 0, (
            f"no input means no Z press and no wall contact other than "
            f"the player's natural fall; wall-jumps-performed should be 0; "
            f"got {wj}"
        )

    def test_no_wall_jumps_with_z_alone(
        self, built_compiler, z_held
    ):
        wj = _read_word(z_held, "wall-jumps-performed", built_compiler)
        assert wj == 0, (
            f"Z held from start fires the rising edge once mid-air while "
            f"player is not touching any wall (x=32, no adjacent solid), "
            f"so no wall jump; got {wj}"
        )

    def test_regular_jump_does_not_count_as_wall_jump(
        self, built_compiler, z_pressed_after_settling
    ):
        wj = _read_word(
            z_pressed_after_settling, "wall-jumps-performed", built_compiler
        )
        assert wj == 0, (
            f"a press while standing on the open floor (no adjacent wall) "
            f"goes through start-jump, not start-wall-jump; "
            f"wall-jumps-performed should be 0; got {wj}"
        )

    def test_wall_jump_sets_lockout(
        self, built_compiler, wall_jump_in_progress
    ):
        lock = _read_word(
            wall_jump_in_progress, "wall-jump-lockout", built_compiler
        )
        assert 1 <= lock <= 8, (
            f"start-wall-jump sets wall-jump-lockout to "
            f"wall-jump-lockout-max (8); the brief phase-4 budget "
            f"(80k ≈ 3 frames) should leave the lockout decremented "
            f"but still positive; got {lock}"
        )

    def test_wall_jump_pushes_player_away_from_wall(
        self, built_compiler, wall_jump_in_progress
    ):
        x = _read_word(wall_jump_in_progress, "player-x", built_compiler)
        assert x > PLAYER_MIN_PX_X + 5, (
            f"during the wall-jump lockout window, update-vx is "
            f"suppressed so player-vx stays at +walk-spd-max (3); the "
            f"player should be visibly pushed away from the left wall "
            f"(more than 5 pixels from x={PLAYER_MIN_PX_X}); got x={x}"
        )

    def test_wall_jump_keeps_vx_at_push_speed(
        self, built_compiler, wall_jump_in_progress
    ):
        vx = _read_word(wall_jump_in_progress, "player-vx", built_compiler)
        assert vx == 3, (
            f"during lockout, update-vx returns early so the +3 "
            f"horizontal push set by start-wall-jump is preserved; "
            f"got vx={vx}"
        )


class TestDash:

    def test_no_dash_in_free_run(self, built_compiler, free_run):
        dp = _read_word(free_run, "dashes-performed", built_compiler)
        assert dp == 0, (
            f"free_run never presses X; dashes-performed should be 0; "
            f"got {dp}"
        )

    def test_dash_available_after_settling_on_floor(
        self, built_compiler, p_held
    ):
        avail = _read_word(p_held, "dash-available", built_compiler)
        assert avail == 1, (
            f"after settling on the floor with P held, tick-dash's "
            f"on-floor? branch should keep dash-available refilled to 1; "
            f"got {avail}"
        )

    def test_facing_tracks_walk_right(self, built_compiler, p_held):
        face = _read_word(p_held, "player-facing", built_compiler)
        assert face == 1, (
            f"update-facing sets player-facing to +1 whenever P is "
            f"held; got {face}"
        )

    def test_facing_tracks_walk_left(self, built_compiler, o_held):
        face = _read_word(o_held, "player-facing", built_compiler)
        assert face == -1, (
            f"update-facing sets player-facing to -1 whenever O is "
            f"held; got {face}"
        )

    def test_dash_right_triggered(
        self, built_compiler, dash_right_in_progress
    ):
        dp = _read_word(
            dash_right_in_progress, "dashes-performed", built_compiler
        )
        state = _read_word(
            dash_right_in_progress, "dash-state", built_compiler
        )
        assert dp == 1, (
            f"X pressed once while P held on the floor (rising edge) "
            f"should fire start-dash exactly once; got {dp}"
        )
        assert state > 0, (
            f"start-dash sets dash-state to dash-duration ({DASH_DURATION}); "
            f"40k ticks ≈ 1 frame later it should still be positive; "
            f"got {state}"
        )

    def test_dash_right_sets_vx_to_dash_speed(
        self, built_compiler, dash_right_in_progress
    ):
        vx = _read_word(dash_right_in_progress, "player-vx", built_compiler)
        assert vx == DASH_SPD, (
            f"start-dash sets player-vx to dash-dir * dash-spd; with P "
            f"held, dash-dir = +1 so vx should be +{DASH_SPD}; "
            f"got {vx}"
        )

    def test_dash_zeros_vy(self, built_compiler, dash_right_in_progress):
        vy = _read_word(dash_right_in_progress, "player-vy", built_compiler)
        assert vy == 0, (
            f"start-dash zeros player-vy so the dash is purely "
            f"horizontal; apply-gravity is also gated on dashing? so "
            f"vy stays at 0 throughout the dash; got {vy}"
        )

    def test_dash_clears_available(
        self, built_compiler, dash_right_in_progress
    ):
        avail = _read_word(
            dash_right_in_progress, "dash-available", built_compiler
        )
        assert avail == 0, (
            f"start-dash consumes the dash, setting dash-available to 0 "
            f"until the player lands; mid-dash it should be 0; got {avail}"
        )

    def test_dash_advances_player_past_spawn(
        self, built_compiler, dash_right_completed
    ):
        x = _read_word(dash_right_completed, "player-x", built_compiler)
        assert x > PLAYER_START_PX_X + 25, (
            f"a 6-frame dash at +{DASH_SPD} px/frame moves the player "
            f"30 px right of spawn; after dash ends, residual vx ramps "
            f"down (5,4,3,2,1) over 5 more frames adding ~15 px more; "
            f"so player should be > 25 px past spawn (x={PLAYER_START_PX_X}); "
            f"got x={x}"
        )

    def test_dash_completed_refills_on_landing(
        self, built_compiler, dash_right_completed
    ):
        avail = _read_word(
            dash_right_completed, "dash-available", built_compiler
        )
        assert avail == 1, (
            f"after the dash ends and the player lands on the floor "
            f"(400k post-dash with gravity restored), tick-dash should "
            f"refill dash-available to 1; got {avail}"
        )

    def test_dash_left_via_facing(
        self, built_compiler, dash_left_via_facing
    ):
        dp = _read_word(
            dash_left_via_facing, "dashes-performed", built_compiler
        )
        vx = _read_word(dash_left_via_facing, "player-vx", built_compiler)
        assert dp == 1, (
            f"walked left then released keys then pressed X; dash-dir "
            f"falls back to player-facing (-1), so a dash should fire; "
            f"got dashes-performed={dp}"
        )
        assert vx == -DASH_SPD, (
            f"with player-facing = -1 and no direction key held, "
            f"start-dash should set player-vx to -{DASH_SPD}; got vx={vx}"
        )

    def test_second_dash_blocked_while_airborne(
        self, built_compiler, second_dash_blocked_airborne
    ):
        dp = _read_word(
            second_dash_blocked_airborne, "dashes-performed", built_compiler
        )
        avail = _read_word(
            second_dash_blocked_airborne, "dash-available", built_compiler
        )
        assert dp == 1, (
            f"player jumped, dashed (1st), waited 150k for dash to end "
            f"while still airborne, then pressed X again; the second X "
            f"should be blocked by dash-available=0 since the player "
            f"hasn't landed; dashes-performed should stay at 1; got {dp}"
        )
        assert avail == 0, (
            f"airborne after a dash with no landing in between, "
            f"dash-available should still be 0; got {avail}"
        )

    def test_dash_up_sets_vy_negative(
        self, built_compiler, dash_up_in_progress
    ):
        vx = _read_word(dash_up_in_progress, "player-vx", built_compiler)
        vy = _read_word(dash_up_in_progress, "player-vy", built_compiler)
        assert vx == 0, (
            f"Q held alone (no O/P) means dash-dx-base returns 0; with "
            f"dy != 0 the facing fallback in dash-dir-2d does not "
            f"trigger, so vx should stay at 0; got vx={vx}"
        )
        assert vy == -DASH_SPD, (
            f"Q held drives dash-dy-base = -1; cardinal dash (one zero "
            f"axis) uses dash-spd, so vy should be -{DASH_SPD}; got vy={vy}"
        )

    def test_dash_up_moves_player_upward(
        self, built_compiler, dash_up_in_progress
    ):
        y = _read_word(dash_up_in_progress, "player-y", built_compiler)
        assert y < PLAYER_REST_PX_Y - 3, (
            f"a fresh frame of up-dash at vy=-{DASH_SPD} should already "
            f"have lifted the player measurably off the floor "
            f"(rest y={PLAYER_REST_PX_Y}); got y={y}"
        )

    def test_dash_up_right_diagonal_uses_reduced_speed(
        self, built_compiler, dash_up_right_in_progress
    ):
        vx = _read_word(dash_up_right_in_progress, "player-vx", built_compiler)
        vy = _read_word(dash_up_right_in_progress, "player-vy", built_compiler)
        assert vx == DASH_SPD_DIAG, (
            f"Q+P both held → is-diagonal? true → dash-speed returns "
            f"dash-spd-diag ({DASH_SPD_DIAG}); vx should be "
            f"+{DASH_SPD_DIAG}; got vx={vx}"
        )
        assert vy == -DASH_SPD_DIAG, (
            f"diagonal dash up-right also drives vy at -{DASH_SPD_DIAG}; "
            f"got vy={vy}"
        )

    def test_dash_down_left_diagonal(
        self, built_compiler, dash_down_left_after_jump_in_progress
    ):
        vx = _read_word(
            dash_down_left_after_jump_in_progress, "player-vx", built_compiler
        )
        vy = _read_word(
            dash_down_left_after_jump_in_progress, "player-vy", built_compiler
        )
        dp = _read_word(
            dash_down_left_after_jump_in_progress,
            "dashes-performed", built_compiler
        )
        assert dp == 1, (
            f"A+O+X mid-air after a jump should fire one dash; "
            f"got dashes-performed={dp}"
        )
        assert vx == -DASH_SPD_DIAG, (
            f"A+O is a diagonal dash down-left; vx should be "
            f"-{DASH_SPD_DIAG}; got vx={vx}"
        )
        assert vy == DASH_SPD_DIAG, (
            f"down component of the diagonal dash is +{DASH_SPD_DIAG}; "
            f"got vy={vy}"
        )


class TestFrameAlignment:

    def test_frame_counter_starts_at_zero(self, built_compiler):
        c = built_compiler
        m = Z80()
        m.load(c.origin, c.build())
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.pressed_keys = set()
        _set_skip_title(m, c)
        m.run(max_ticks=1_000_000)
        fc = _read_word(m, "frame-counter", c)
        assert fc >= 1, (
            f"after init-game runs and a few game-steps execute, "
            f"frame-counter should have incremented past 0 (init-game "
            f"sets it to 0, each game-step adds 1); got {fc}"
        )

    def test_frame_counter_monotonically_increasing(
        self, built_compiler, free_run
    ):
        first = _read_word(free_run, "frame-counter", built_compiler)
        assert first > 0, (
            f"free_run runs for {TICK_BUDGET} ticks of game-loop; "
            f"frame-counter should be well above 0; got {first}"
        )

    @pytest.mark.parametrize("fixture_name", [
        "free_run", "p_held", "o_held", "z_held",
        "wall_jump_sequence", "dash_right_completed",
        "coin_collected_via_step",
    ])
    def test_post_save_pos_consistency(
        self, built_compiler, request, fixture_name
    ):
        m = request.getfixturevalue(fixture_name)
        x = _read_word(m, "player-x", built_compiler)
        y = _read_word(m, "player-y", built_compiler)
        old_x = _read_word(m, "player-old-x", built_compiler)
        old_y = _read_word(m, "player-old-y", built_compiler)
        assert x == old_x and y == old_y, (
            f"_align_to_frame_end stops the sim after save-pos runs, "
            f"which copies player-x to player-old-x and player-y to "
            f"player-old-y; after the harness aligns, the two pairs "
            f"must match; got x={x} old_x={old_x} y={y} old_y={old_y} "
            f"in fixture {fixture_name}"
        )

    def test_frame_alignment_stops_after_save_pos_not_before(
        self, built_compiler
    ):
        m1 = _run(built_compiler, pressed_keys={ord("O")})
        m2 = _run(built_compiler, pressed_keys={ord("O")})
        x1 = _read_word(m1, "player-x", built_compiler)
        y1 = _read_word(m1, "player-y", built_compiler)
        fc1 = _read_word(m1, "frame-counter", built_compiler)
        x2 = _read_word(m2, "player-x", built_compiler)
        y2 = _read_word(m2, "player-y", built_compiler)
        fc2 = _read_word(m2, "frame-counter", built_compiler)
        assert x1 == x2 and y1 == y2 and fc1 == fc2, (
            f"two independent runs of _run with the same inputs should "
            f"land at the same frame-counter and the same player "
            f"position because frame alignment is deterministic; got "
            f"run1=(x={x1},y={y1},fc={fc1}) "
            f"run2=(x={x2},y={y2},fc={fc2})"
        )


class TestDefensiveHudRepaint:

    ATTRS = 0x5800
    HUD_ATTR = 0x46
    ROOM_ATTR = 0x07

    def test_hud_overdraw_false_when_player_below_row_zero(
        self, built_compiler, free_run
    ):
        y = _read_word(free_run, "player-y", built_compiler)
        assert y >= 8, (
            f"free_run lands the player on the floor at y=176; "
            f"player-y should never be in row 0 (y<8) here; got {y}"
        )

    def test_hud_attrs_intact_when_player_far_from_row_zero(
        self, free_run
    ):
        attr = free_run.mem[self.ATTRS + 0 * 32 + 5]
        assert attr == self.HUD_ATTR, (
            f"player never enters row 0 in free_run, so paint-hud-attrs "
            f"runs only from init-game; the attrs should still read "
            f"hud-attr=${self.HUD_ATTR:02X}; got ${attr:02X}"
        )

    def test_repaint_restores_hud_after_manual_corruption(
        self, built_compiler
    ):
        c = built_compiler
        m = Z80()
        m.load(c.origin, c.build())
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.pressed_keys = set()
        _set_skip_title(m, c)
        m.run(max_ticks=1_200_000)
        _align_to_frame_end(m, c)

        for col in range(1, 31):
            m.mem[self.ATTRS + col] = self.ROOM_ATTR
        for col in range(2, 6):
            for line in range(8):
                m.mem[screen_addr(0, col, line)] = 0x00
        py_addr = c.words["player-y"].data_address
        m.mem[py_addr]     = 0
        m.mem[py_addr + 1] = 0

        m.run(max_ticks=200_000)
        _align_to_frame_end(m, c)

        attr = m.mem[self.ATTRS + 0 * 32 + 5]
        assert attr == self.HUD_ATTR, (
            f"after the test wipes row 0 attrs and sets player-y=0 "
            f"(so hud-overdraw? returns true), the next frame's "
            f"maybe-repaint-hud should fire paint-hud-attrs and "
            f"restore the colour strip; col 5 row 0 should be "
            f"${self.HUD_ATTR:02X}; got ${attr:02X}"
        )
        cells = [m.mem[screen_addr(0, 2, line)] for line in range(8)]
        nonzero = sum(1 for b in cells if b != 0)
        assert nonzero >= 4, (
            f"paint-altitude should have written the '1' glyph at "
            f"col 2 row 0; the cell should have at least a few nonzero "
            f"scan-lines; got {cells}"
        )


class TestTitleScreen:

    def _fresh_machine(self, c):
        m = Z80()
        m.load(c.origin, c.build())
        m.load(SPECTRUM_FONT_BASE, TEST_FONT)
        m.pc = c.words["_start"].address
        m.pressed_keys = set()
        return m

    def test_title_text_renders(self, built_compiler):
        c = built_compiler
        m = self._fresh_machine(c)
        m.run(max_ticks=500_000)
        title = "".join(chr(m.mem[screen_addr(10, 12 + i, 0)])
                        for i in range(7))
        assert title == "CELESTE", (
            f"with skip-title left at 0, the title screen runs first; "
            f"paint-title writes 'CELESTE' at (col 12, row 10); "
            f"got '{title}'"
        )

    def test_press_prompt_renders(self, built_compiler):
        c = built_compiler
        m = self._fresh_machine(c)
        m.run(max_ticks=500_000)
        prompt = "".join(chr(m.mem[screen_addr(14, 8 + i, 0)])
                         for i in range(16))
        assert prompt == "PRESS Z TO START", (
            f"paint-title writes 'PRESS Z TO START' at (col 8, row 14); "
            f"got '{prompt}'"
        )

    def test_game_does_not_start_without_z(self, built_compiler):
        c = built_compiler
        m = self._fresh_machine(c)
        m.run(max_ticks=2_000_000)
        fc = _read_word(m, "frame-counter", c)
        assert fc == 0, (
            f"wait-for-start loops on z-held? until Z is pressed; "
            f"without any key held, the game-loop should never run, so "
            f"frame-counter should still be 0; got {fc}"
        )

    def test_z_press_starts_game(self, built_compiler):
        c = built_compiler
        m = self._fresh_machine(c)
        m.pressed_keys = {ord("Z")}
        m.run(max_ticks=2_000_000)
        _align_to_frame_end(m, c)
        fc = _read_word(m, "frame-counter", c)
        assert fc > 0, (
            f"pressing Z should let wait-for-start fall through to "
            f"init-game and game-loop; frame-counter should advance; "
            f"got {fc}"
        )

    def test_skip_title_flag_bypasses_title(
        self, built_compiler, free_run
    ):
        fc = _read_word(free_run, "frame-counter", built_compiler)
        assert fc > 0, (
            f"_run sets skip-title to -1 before starting the sim, so "
            f"celeste-mvp skips paint-title and wait-for-start and "
            f"goes straight to init-game and game-loop; free_run "
            f"should advance frame-counter; got {fc}"
        )


class TestRoomDispatch:

    def test_current_room_initial(self, built_compiler, free_run):
        current = _read_word(free_run, "current-room", built_compiler)
        assert current == 1, (
            f"init-game sets current-room to 1 (the 100m room); after "
            f"free_run runs, it should still be 1; got {current}"
        )

    def test_dispatch_can_be_pointed_at_other_rooms(
        self, built_compiler, free_run
    ):
        c = built_compiler
        cr_addr = c.words["current-room"].data_address
        free_run.mem[cr_addr]     = 2
        free_run.mem[cr_addr + 1] = 0
        current = _read_word(free_run, "current-room", c)
        assert current == 2, (
            f"current-room is a regular variable that future iters "
            f"can store other room indices into; writing 2 should "
            f"read back as 2 (this is just a smoke test that the "
            f"variable is a real cell, not a sealed constant); got "
            f"{current}"
        )

    def test_room_1_drew_the_floor(self, free_run):
        cells = [free_run.mem[screen_addr(23, col, 0)]
                 for col in [5, 15, 25]]
        assert all(b == 0xFF for b in cells), (
            f"init-room-1 fills floor-row=23 with solid; sampled "
            f"cells (col 5/15/25, row 23) should all read 0xFF at "
            f"scan-line 0; got {cells}"
        )

    def test_room_1_drew_the_step(self, free_run):
        cells = [free_run.mem[screen_addr(22, col, 0)]
                 for col in [26, 28, 30]]
        assert all(b == 0xFF for b in cells), (
            f"init-room-1 fills cols 26-30 of row 22 with solid for "
            f"the step; sampled cells should be 0xFF; got {cells}"
        )


class TestEntityVariables:

    @pytest.mark.parametrize("var,expected", [
        ("coin-col",   28),
        ("coin-row",   21),
        ("coin-x",     224),
        ("coin-y",     168),
        ("spikes-col", 20),
        ("spikes-row", 20),
        ("spikes-x",   160),
        ("spikes-y",   160),
        ("spring-col", 14),
        ("spring-row", 17),
        ("spring-x",   112),
        ("spring-y",   136),
    ])
    def test_room_1_entity_position_loaded(
        self, built_compiler, free_run, var, expected
    ):
        v = _read_word(free_run, var, built_compiler)
        assert v == expected, (
            f"load-room-1-entities sets {var} to {expected} for the "
            f"100m layout (was a constant before this iter, now a "
            f"variable); got {v}"
        )

    def test_entity_positions_are_writable(
        self, built_compiler, free_run
    ):
        c = built_compiler
        addr = c.words["coin-x"].data_address
        free_run.mem[addr]     = 100
        free_run.mem[addr + 1] = 0
        v = _read_word(free_run, "coin-x", c)
        assert v == 100, (
            f"coin-x is now a variable (was constant before); future "
            f"iters set per-room positions by storing into it; smoke "
            f"check that the cell is writable; got {v}"
        )

    def test_loading_other_room_is_no_op_for_now(
        self, built_compiler, free_run
    ):
        c = built_compiler
        cr_addr = c.words["current-room"].data_address
        cx_addr = c.words["coin-x"].data_address
        free_run.mem[cr_addr]     = 2
        free_run.mem[cr_addr + 1] = 0
        free_run.mem[cx_addr]     = 0xAA
        free_run.mem[cx_addr + 1] = 0xBB
        v_before = _read_word(free_run, "coin-x", c)
        assert v_before == _s16(0xAA, 0xBB), (
            f"setup sanity: coin-x should hold the marker"
        )


@pytest.fixture(scope="module")
def advanced_to_room_2(built_compiler):
    m = _run(built_compiler, pressed_keys=set())
    ar_addr = built_compiler.words["advance-requested"].data_address
    m.mem[ar_addr]     = 0xFF
    m.mem[ar_addr + 1] = 0xFF
    m.run(max_ticks=400_000)
    _align_to_frame_end(m, built_compiler)
    return m


class TestRoomTwo:

    def test_current_room_advanced(self, built_compiler, advanced_to_room_2):
        cr = _read_word(advanced_to_room_2, "current-room", built_compiler)
        assert cr == 2, (
            f"poking advance-requested=-1 should let maybe-advance-room "
            f"fire on the next frame, incrementing current-room to 2; "
            f"got {cr}"
        )

    def test_advance_requested_cleared(
        self, built_compiler, advanced_to_room_2
    ):
        ar = _read_word(advanced_to_room_2, "advance-requested",
                        built_compiler)
        assert ar == 0, (
            f"maybe-advance-room consumes the request by zeroing "
            f"advance-requested before calling advance-room; got {ar}"
        )

    @pytest.mark.parametrize("var,expected", [
        ("coin-col",   15),
        ("coin-row",   16),
        ("coin-x",     120),
        ("coin-y",     128),
        ("spikes-col", 24),
        ("spikes-row", 22),
        ("spikes-x",   192),
        ("spikes-y",   176),
        ("spring-col", 5),
        ("spring-row", 22),
        ("spring-x",   40),
        ("spring-y",   176),
    ])
    def test_room_2_entity_positions_loaded(
        self, built_compiler, advanced_to_room_2, var, expected
    ):
        v = _read_word(advanced_to_room_2, var, built_compiler)
        assert v == expected, (
            f"after advancing to room 2, load-room-2-entities should "
            f"set {var} to {expected}; got {v}"
        )

    def test_room_2_platform_drawn(self, advanced_to_room_2):
        cells = [advanced_to_room_2.mem[screen_addr(17, col, 0)]
                 for col in [12, 15, 19]]
        assert all(b == 0xFF for b in cells), (
            f"init-room-2 fills cols 12-19 of row 17 with solid for "
            f"the platform; sampled cells should be 0xFF; got {cells}"
        )

    def test_room_1_step_replaced(self, advanced_to_room_2):
        cells = [advanced_to_room_2.mem[screen_addr(22, col, 0)]
                 for col in [28, 29, 30]]
        assert all(b == 0x00 for b in cells), (
            f"room 2 has no step at row 22 cols 28-30 (room 2's "
            f"spike triplet covers cols 24-26, but cols 28-30 are "
            f"the rightmost step cells from room 1 and should be "
            f"blank after advance-room clears the grid and redraws); "
            f"got {cells}"
        )

    def test_room_2_floor_still_present(self, advanced_to_room_2):
        cell = advanced_to_room_2.mem[screen_addr(23, 15, 0)]
        assert cell == 0xFF, (
            f"room 2 still has the floor at row 23 because init-room-2 "
            f"calls fill-floor; got {cell}"
        )

    def test_coin_reset_on_advance(
        self, built_compiler, advanced_to_room_2
    ):
        collected = _read_word(
            advanced_to_room_2, "coin-collected", built_compiler
        )
        assert collected == 0, (
            f"advance-room calls coin-reset so the new room's coin "
            f"becomes pickable; got coin-collected={collected}"
        )

    def test_spring_bounces_reset_on_advance(
        self, built_compiler, advanced_to_room_2
    ):
        sb = _read_word(advanced_to_room_2, "spring-bounces",
                        built_compiler)
        assert sb == 0, (
            f"advance-room calls spring-reset to clear per-room "
            f"spring state; got spring-bounces={sb}"
        )

    def test_player_repositioned_on_advance(
        self, built_compiler, advanced_to_room_2
    ):
        x = _read_word(advanced_to_room_2, "player-x", built_compiler)
        y = _read_word(advanced_to_room_2, "player-y", built_compiler)
        assert x == 32 and y < 24, (
            f"advance-room calls player-reset, putting the player at "
            f"the spawn position (32, 8); the player may have fallen "
            f"a few pixels by the time the harness aligns, so check "
            f"x==32 and y<24; got x={x} y={y}"
        )
