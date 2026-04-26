\ Sierpinski triangle rendered in the Spectrum attribute grid.
\
\ Exercises every M6 feature:
\   - INCLUDE/REQUIRE resolving paths relative to the including file
\   - REQUIRE deduplication (lib/math.fs is required by both main and screen.fs)
\   - auto-bundled stdlib (cls comes from stdlib/core.fs)
\
\ Build:  zt build examples/sierpinski/main.fs -o build/sierpinski.sna \
\              --map build/sierpinski.map

require lib/math.fs
require lib/screen.fs

56 constant cell-on     \ bright white paper, black ink
0  constant cell-off    \ black paper + black ink = hidden

\ pick the attribute for cell (col, row): on when (col AND row) is zero
: sierp-attr  ( col row -- attr )
    bit-clear? if cell-on else cell-off then ;

\ render the triangle into the entire attribute grid
: draw  ( -- )
    scr-rows 0 do
        scr-cols 0 do
            i j sierp-attr i j attr!
        loop
    loop ;

\ entry point: clear the screen, draw the triangle, halt
: main
    7 0 cls
    draw
    halt ;
