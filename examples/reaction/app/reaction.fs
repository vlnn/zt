\ One-key reaction-time game.  Each round picks a digit, waits a random
\ delay so the player can't anticipate, displays it, and times how long
\ until the matching key is pressed.  The session keeps a running
\ average across rounds; the loop runs forever.

require ../lib/rng.fs
require ../lib/timing.fs

10  constant digit-count
25  constant min-delay
100 constant max-delay

variable total-ms
variable round-count


\ Picking a challenge
\ ──────────────────
\ A challenge is a digit 0..9 plus a pre-prompt delay drawn from
\ [min-delay, max-delay) frames.  digit>char converts the integer to
\ its ASCII codepoint so the same digit can be both displayed and
\ compared against the player's keypress.

: digit>char    ( n -- c )           48 + ;
: show-digit    ( n -- )             digit>char emit ;

: pick-digit    ( -- 0..9 )          digit-count random ;
: random-delay  ( -- frames )        max-delay min-delay - random min-delay + ;


\ Waiting for the player
\ ──────────────────────
\ pause blocks for a known number of frames — used for the pre-prompt
\ delay.  wait-for-key counts frames *while* polling, so the caller
\ gets both the key and the elapsed time in one call.  wait-for-release
\ is the cleanup: without it the next round's wait-for-key would see
\ the same key still held and return instantly with zero elapsed time.

: pause         ( frames -- )        0 do wait-frame loop ;

: wait-for-key  ( -- key frames )
    0
    begin  wait-frame 1+  key?  until
    key swap ;

: wait-for-release  ( -- )   begin wait-frame key? 0= until ;
: await-any-key     ( -- )   wait-for-release wait-for-key 2drop ;


\ Judging the answer
\ ──────────────────
\ check-key takes the digit that was shown and the byte that was typed,
\ converts the digit to its ASCII form, and compares.  The flag goes
\ straight to verdict for printing — combined this way, the round's
\ result is a single line of code.

: check-key     ( shown typed -- correct? )  swap digit>char = ;
: verdict       ( correct? -- )              if ." correct! " else ." wrong! " then ;


\ Statistics and reporting
\ ────────────────────────
\ total-ms accumulates milliseconds across every round of the session;
\ round-count is the divisor for the running average.  finish-round is
\ the after-round pipeline: record this round's time, print it, print
\ the running average, and prompt for the next round.  Every round of
\ the session goes through it.

: reset-stats   ( -- )               0 total-ms !  0 round-count ! ;
: record-round  ( ms -- )            total-ms +!  1 round-count +! ;
: avg-ms        ( -- ms )            total-ms @ round-count @ / ;

: print-result  ( ms -- )            ." reacted in " u. ." ms" cr ;
: print-avg     ( -- )               ." average: "   avg-ms u. ." ms" cr ;
: print-any-key ( -- )               ." PRESS ANY KEY TO CONTINUE" cr ;

: finish-round  ( ms -- )            dup record-round print-result print-avg print-any-key ;


\ Playing rounds
\ ──────────────
\ A round: clear the screen, show "ready", pause unpredictably, show
\ the digit, time the response, judge it, report.  game-loop runs
\ play-round forever — there's no win condition, just an unbounded
\ session.

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
