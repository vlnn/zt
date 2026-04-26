\ app/sounds.fs — BEEP effects tuned for Mined-Out.

require core.fs

\ short footstep click
: click          ( -- )          1 30 beep ;

\ rising tone for n adjacent mines (silent if n is zero)
: proximity      ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

\ rapid descending sweep with flashing border — mine detonation
: explosion      ( -- )
    40 0 do  i 7 mod border  2 40 i - beep  loop
    0 border ;

\ rising tones with cycling border colours — level-complete fanfare
: fanfare        ( -- )
    10 0 do  i 2 +  7 mod  border  3 100 i 10 * - beep  loop
    0 border ;

\ ascending chirp — damsel rescued
: rescue-chirp   ( -- )
    8 0 do  2 30 i 8 * + beep  loop ;

\ low buzz — bug hiss
: bug-hiss       ( -- )          1 100 beep ;

\ falling sweep with flicker — passing through the gap
: gap-chirp      ( -- )
    20 0 do  i 2 mod border  2 45 i - beep  loop
    0 border ;
