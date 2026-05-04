# Tetris

A colourful Tetris with three preset levels for the ZX Spectrum, written
in zt's Forth dialect and cross-compiled to a 48k snapshot.

Each level starts with pre-placed debris in the bottom rows. The player
wins by clearing every preset cell — fall through all three levels and
the game declares victory.

```
       SCORE 000000   LV 1                    NEXT
                                              ────
                      ┌──────────┐             ▓▓▓
                      │          │             ▓▓
                      │   ░      │
                      │   ░      │            LEFT
                      │   ░      │             ─── 09
                      │   ░      │
                      │          │
                      │          │
                      │          │
                      │   ┐      │
                      │  ▓▓▓     │
                      │   ▓      │
                      │          │
                      │██████████│  ← preset, gap at col 0
                      └──────────┘
```

## Build & run

```sh
uv run python -m zt.cli build examples/tetris/main.fs -o build/tetris.sna
fuse build/tetris.sna           # any ZX Spectrum emulator
```

## Controls

Three input methods are wired up in parallel — the game OR's them together
so you can use whichever your emulator forwards:

| Action       | Kempston | Sinclair P1 | Keyboard |
| ------------ | -------- | ----------- | -------- |
| Move left    | left     | 6           | O        |
| Move right   | right    | 7           | P        |
| Soft drop    | down     | 8           | A        |
| Rotate       | up       | 0           | M        |

Rotation latches on key-press edges so holding the rotate button rotates
exactly once.

## Levels

| # | Layout                              | Presets | Attribute |
| - | ----------------------------------- | ------- | --------- |
| 1 | row 17, gap at col 0                | 9       | green     |
| 2 | rows 16-17, alternating gaps        | 18      | red       |
| 3 | rows 14-17, paired gaps mid-row     | 34      | magenta   |

Preset cells carry bit 7 in the playfield byte; line-clear counts how many
preset cells were in each cleared row and decrements `preset-remaining`.
When that hits zero the level advances; if a piece fails to spawn (the
playfield blocked the spawn position) the game ends.

## Module layout

```
main.fs              entry point
lib/
  sprites.fs         block / wall / empty 8x8 tiles
  pieces.fs          7 tetrominoes, 4 rotations each, attribute table
  playfield.fs       10x18 grid, drawing, line detection, compaction
  piece.fs           active piece state, fits-test, move/rotate, lock
  controls.fs        Kempston + Sinclair + QAOP combined into in-* flags
  audio.fs           beeper SFX + IM 2 hook seam for music later
  levels.fs          three preset row-bitmap layouts + level-load
  score.fs           score, level, preset-remaining, hud-dirty
  game.fs            HUD, walls, frame loop, level lifecycle, entry
tests/
  test_tetris.py     end-to-end pytest suite (105 cases)
  test_playfield.fs  Forth-level unit tests for line detection (10 cases)
```

## Design notes

**Playfield encoding.** Each cell is one byte — 0 means empty, otherwise
the low 7 bits are a Spectrum attribute byte and bit 7 marks preset
debris. Line clear walks rows bottom-up with src/dst pointers (`pf-compact`
in `playfield.fs`); full rows advance src only, non-full rows copy
src→dst with `cmove`. After src falls off the top, rows 0..dst inclusive
are cleared.

**Piece movement.** Every motion is a "try" — `piece-fits?` checks bounds
and collisions for a hypothetical `(id, rot, col, row)`; only on success
does `piece-try-place` commit to `piece-cur-*`. Movement, rotation and
gravity all build on this single primitive.

**Audio seam.** `audio-isr` in `lib/audio.fs` is documented but stubbed.
To add an AY tracker later, write the ISR in raw assembly and call
`['] audio-isr im2-handler! ei` from `audio-init` — the rest of the
game keeps firing `audio-on-*` SFX hooks unchanged.

**Kempston filter.** When no joystick is attached, port `$1F` floats high
and reads as `$FF` on real hardware (and the simulator). The masked
result `$1F` would be all directions plus fire pressed simultaneously,
which a real joystick can't produce — `kempston` filters that case to
zero so a missing interface doesn't phantom-press every direction.

## Test strategy

```sh
uv run pytest examples/tetris/                 # 115 tests, ~15s
uv run pytest examples/tetris/tests/test_playfield.fs   # Forth-only
uv run pytest examples/tetris/tests/test_tetris.py      # Python-only
```

Tests come in two layers. `test_playfield.fs` is a set of Forth-level
unit tests that drive `pf-row-full?` and `pf-compact` against a
hand-stamped grid; the conftest auto-discovers `test-*` words and runs
each in its own compiled snapshot. `test_tetris.py` builds the full
game once and exercises gameplay end-to-end — joystick movement,
gravity, lock detection, level loading — by reading state variables out
of the simulated Z80 memory after a bounded run.
