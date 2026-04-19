require ../lib/rng.fs
require ../lib/timing.fs

10  constant digit-count
25  constant min-delay
100 constant max-delay

variable total-ms
variable round-count

: digit>char    ( n -- c )           48 + ;
: show-digit    ( n -- )             digit>char emit ;
: pick-digit    ( -- 0..9 )          digit-count random ;
: random-delay  ( -- frames )        max-delay min-delay - random min-delay + ;

: pause         ( frames -- )        0 do wait-frame loop ;

: wait-for-key  ( -- key frames )
    0
    begin  wait-frame 1+  key?  until
    key swap ;

: wait-for-release  ( -- )   begin wait-frame key? 0= until ;
: await-any-key     ( -- )   wait-for-release wait-for-key 2drop ;

: check-key     ( shown typed -- correct? )  swap digit>char = ;
: verdict       ( correct? -- )              if ." correct! " else ." wrong! " then ;

: reset-stats   ( -- )               0 total-ms !  0 round-count ! ;
: record-round  ( ms -- )            total-ms +!  1 round-count +! ;
: avg-ms        ( -- ms )            total-ms @ round-count @ / ;

: print-result  ( ms -- )            ." reacted in " u. ." ms" cr ;
: print-avg     ( -- )               ." average: "   avg-ms u. ." ms" cr ;
: print-any-key ( -- )               ." PRESS ANY KEY TO CONTINUE" cr ;

: finish-round  ( ms -- )            dup record-round print-result print-avg print-any-key ;

: play-round    ( -- )
    7 0 cls
    ." ready..." cr
    random-delay pause
    ." >> " pick-digit dup show-digit cr
    wait-for-key >r
    check-key verdict
    r> frames>ms finish-round
    await-any-key ;

: game-loop     ( -- )               begin play-round again ;
