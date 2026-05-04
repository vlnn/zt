\ Sierpinski triangle rendered into the Spectrum attribute grid.
\ Doubles as a smoke test for the M6 milestone: paths in `require`
\ resolve relative to the including file (lib/math.fs is reached one
\ way from here, another way from screen.fs), the resolver dedups so
\ math.fs loads once, and `cls` comes from the auto-bundled stdlib.
\
\ Build:  zt build examples/sierpinski/main.fs -o build/sierpinski.sna \
\              --map build/sierpinski.map

require lib/math.fs
require lib/screen.fs


\ The grid
\ ────────
\ A cell is on when its (col, row) pair shares no bits — the AND-zero
\ test from math.fs lights every position whose binary coordinates have
\ no overlap, which is exactly the Sierpinski triangle.  Attribute byte
\ 56 is bright white paper with black ink; 0 is black-on-black.

56 constant cell-on
0  constant cell-off

: sierp-attr  ( col row -- attr )
    bit-clear? if cell-on else cell-off then ;

: draw  ( -- )
    scr-rows 0 do
        scr-cols 0 do
            i j sierp-attr i j attr!
        loop
    loop ;

: main
    7 0 cls
    draw
    halt ;
