\ Attribute-grid plasma.
\
\ Formula:  attr(col, row, t) = paper(wave[(col+t) mod 32] XOR wave[(row+t) mod 32])
\ `wave` is a 32-entry triangle wave in [0,7] so the XOR stays in [0,7].
\ Shifting that 3 left lands it in the PAPER bits; the BRIGHT bit (64) makes
\ the colors pop.
\
\ M10 placeholder — intentionally kept minimal:
\   - triangle wave instead of a real sine table
\   - no timing; just redraws as fast as the threaded code can go
\   - no double-buffering
\
\ The multi-file layout is what's being demonstrated, not the effect.

require ../lib/math.fs
require ../lib/screen.fs

create wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,

variable phase

: wave@  ( i -- n )        mod32 wave + c@ ;

: plasma-cell  ( col row -- attr )
    phase @ + wave@ swap
    phase @ + wave@
    xor
    3 lshift 64 or ;

: draw  ( -- )
    scr-rows 0 do
        scr-cols 0 do
            i j plasma-cell i j attr!
        loop
    loop ;

: step  ( -- )  1 phase +! ;

: animate
    begin draw step again ;
