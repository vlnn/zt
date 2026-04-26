require ../lib/rng.fs
require ../lib/timing.fs

10  constant digit-count
25  constant min-delay
100 constant max-delay

variable total-ms
variable round-count

\ convert a 0..9 value to its ASCII digit code
: digit>char    ( n -- c )           48 + ;
\ print a 0..9 digit on screen
: show-digit    ( n -- )             digit>char emit ;
\ pick a random digit in 0..9 to challenge the player with
: pick-digit    ( -- 0..9 )          digit-count random ;
\ pick a random pre-prompt delay in [min-delay, max-delay) frames
: random-delay  ( -- frames )        max-delay min-delay - random min-delay + ;

\ block for the given number of frames
: pause         ( frames -- )        0 do wait-frame loop ;

\ wait for any keypress and return the key plus the elapsed frame count
: wait-for-key  ( -- key frames )
    0
    begin  wait-frame 1+  key?  until
    key swap ;

\ block until no key is held
: wait-for-release  ( -- )   begin wait-frame key? 0= until ;
\ wait for the previous key to be released, then for any new keypress
: await-any-key     ( -- )   wait-for-release wait-for-key 2drop ;

\ true if typed (ASCII) matches shown (digit)
: check-key     ( shown typed -- correct? )  swap digit>char = ;
\ print "correct!" or "wrong!" based on the flag
: verdict       ( correct? -- )              if ." correct! " else ." wrong! " then ;

\ zero out cumulative stats at the start of a session
: reset-stats   ( -- )               0 total-ms !  0 round-count ! ;
\ add ms to total time and bump the round counter
: record-round  ( ms -- )            total-ms +!  1 round-count +! ;
\ mean reaction time over all played rounds
: avg-ms        ( -- ms )            total-ms @ round-count @ / ;

\ print "reacted in N ms"
: print-result  ( ms -- )            ." reacted in " u. ." ms" cr ;
\ print the running average reaction time
: print-avg     ( -- )               ." average: "   avg-ms u. ." ms" cr ;
\ print the standard prompt to continue
: print-any-key ( -- )               ." PRESS ANY KEY TO CONTINUE" cr ;

\ record this round's time and print result, average and prompt
: finish-round  ( ms -- )            dup record-round print-result print-avg print-any-key ;

\ run a single round: countdown, prompt, await keypress, judge, report
: play-round    ( -- )
    7 0 cls
    ." ready..." cr
    random-delay pause
    ." >> " pick-digit dup show-digit cr
    wait-for-key >r
    check-key verdict
    r> frames>ms finish-round
    await-any-key ;

\ run rounds forever
: game-loop     ( -- )               begin play-round again ;
