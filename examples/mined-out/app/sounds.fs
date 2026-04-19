\ app/sounds.fs — BEEP effects tuned for Mined-Out.
\
\ These shadow a couple of stdlib names (click) on purpose: the BASIC uses
\ tighter, punchier values than the generic stdlib defaults.

: click          ( -- )          1 30 beep ;

: proximity      ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

: explosion      ( -- )
    40 0 do  2 40 i - beep  loop ;

: fanfare        ( -- )
    10 0 do  3 100 i 10 * - beep  loop ;

: rescue-chirp   ( -- )
    8 0 do  2 30 i 8 * + beep  loop ;

: bug-hiss       ( -- )          1 100 beep ;
