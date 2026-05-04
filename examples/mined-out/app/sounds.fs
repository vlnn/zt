\ BEEP-based sound effects, tuned for Mined-Out.  Each one is a
\ short one-liner over the stdlib `beep` (length, pitch) and `border`
\ primitives.  The mine explosion and gap-chirp combine pitch sweeps
\ with rapid border flickering for visual impact alongside the audio.

require core.fs

: click          ( -- )          1 30 beep ;

: proximity      ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

: explosion      ( -- )
    40 0 do  i 7 mod border  2 40 i - beep  loop
    0 border ;

: fanfare        ( -- )
    10 0 do  i 2 +  7 mod  border  3 100 i 10 * - beep  loop
    0 border ;

: rescue-chirp   ( -- )
    8 0 do  2 30 i 8 * + beep  loop ;

: bug-hiss       ( -- )          1 100 beep ;

: gap-chirp      ( -- )
    20 0 do  i 2 mod border  2 45 i - beep  loop
    0 border ;
