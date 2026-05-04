\ A colourful Tetris with three preset levels.  Each level starts with
\ pre-placed debris that the player must clear in order to advance;
\ score and preset-remaining update as lines clear.  Controls cover
\ Kempston joystick (port $1F), Sinclair joystick (keys 6/7/8/9/0),
\ and the QAOP+space keyboard layout simultaneously.
\
\ Build:  zt build examples/tetris/main.fs -o build/tetris.sna
\
\ Module layout:
\   sprites.fs    block / wall / empty 8x8 tiles
\   pieces.fs     7 tetrominoes, 4 rotations each, attribute table
\   playfield.fs  10x18 grid, drawing, line detection + compaction
\   piece.fs      active piece state, fits-test, move/rotate, lock
\   controls.fs   Kempston + Sinclair + QAOP combined into in-* flags
\   audio.fs      beeper SFX + IM 2 hook seam for music later
\   levels.fs     three preset row-bitmap layouts + level-load
\   score.fs      score, level, preset-remaining, hud-dirty
\   game.fs       HUD, walls, frame loop, level lifecycle, entry

require lib/game.fs

: main    tetris halt ;
