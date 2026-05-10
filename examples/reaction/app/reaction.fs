\ One-key reaction-time game.  Each round picks a digit, waits a random
\ delay so the player can't anticipate, displays it, and times how long
\ until the matching key is pressed.  The session keeps a running
\ average across rounds; the loop runs forever.
\
\ READY..., the digit, and the verdict (GREAT! / WRONG!) are rendered
\ as 8x8 attribute-cell blocks via lib/big-text.fs — each font pixel
\ becomes one whole 8x8 attribute square, so a single character
\ occupies a 64x64-pixel patch of solid colour with no glyph pixels
\ underneath.  Reaction stats stay in normal-sized text below.

require ../lib/rng.fs
require ../lib/timing.fs
require ../lib/big-text.fs

10  constant digit-count
25  constant min-delay
100 constant max-delay

7   constant paper-white
6   constant paper-yellow
5   constant paper-cyan
4   constant paper-green
2   constant paper-red

16  constant stats-row

variable total-ms
variable round-count


\ Picking a challenge
\ ──────────────────

: digit>char    ( n -- c )           48 + ;

: pick-digit    ( -- 0..9 )          digit-count random ;
: random-delay  ( -- frames )        max-delay min-delay - random min-delay + ;


\ Painting big colour text
\ ────────────────────────
\ Off-cells use the same paper as the cls background, so they blend
\ in and only the lit cells stand out as a coloured glyph.

: bright-paper  ( paper -- attr )    0 swap colour bright ;
: blend-attr    ( -- attr )          0 paper-white colour ;
: paint-with    ( paper -- )         bright-paper blend-attr big-colours ;

: show-ready    ( -- )
    paper-yellow paint-with
    s" READ" 0 0 big-type
    s" Y..." 0 8 big-type ;

: show-digit    ( n -- )
    paper-cyan paint-with
    digit>char 12 4 big-emit ;

: show-great    ( -- )
    paper-green paint-with
    s" GRE" 4 0 big-type
    s" AT!" 4 8 big-type ;

: show-wrong    ( -- )
    paper-red paint-with
    s" WRO" 4 0 big-type
    s" NG!" 4 8 big-type ;

: show-verdict  ( correct? -- )      if show-great else show-wrong then ;


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

: check-key     ( shown typed -- correct? )  swap digit>char = ;


\ Statistics and reporting
\ ────────────────────────
\ total-ms accumulates milliseconds across every round of the session;
\ round-count is the divisor for the running average.  finish-round is
\ the after-round pipeline: position the cursor below the big verdict,
\ record this round's time, print it, print the running average, and
\ prompt for the next round.

: reset-stats   ( -- )               0 total-ms !  0 round-count ! ;
: record-round  ( ms -- )            total-ms +!  1 round-count +! ;
: avg-ms        ( -- ms )            total-ms @ round-count @ / ;

: print-result  ( ms -- )            ." reacted in " u. ." ms" cr ;
: print-avg     ( -- )               ." average: "   avg-ms u. ." ms" cr ;
: print-any-key ( -- )               ." PRESS ANY KEY TO CONTINUE" cr ;

: at-stats      ( -- )               0 stats-row at-xy ;
: finish-round  ( ms -- )
    at-stats  dup record-round  print-result print-avg print-any-key ;


\ Playing rounds
\ ──────────────
\ A round: clear, show big READY..., pause unpredictably, clear, show
\ the big digit, time the response, judge it, clear, show the big
\ verdict, then print stats below.  game-loop runs play-round forever
\ — there's no win condition, just an unbounded session.

: play-round    ( -- )
    7 0 cls  show-ready
    random-delay pause
    7 0 cls  pick-digit dup show-digit
    wait-for-key >r
    check-key
    7 0 cls  show-verdict
    r> frames>ms finish-round
    await-any-key ;

: game-loop     ( -- )               begin play-round again ;
