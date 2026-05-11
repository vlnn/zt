\ One-key reaction-time game.  Each round picks a digit, waits a random
\ delay so the player can't anticipate, displays it, and times how long
\ until the matching key is pressed.  The session keeps a running
\ average across rounds; the loop runs forever.
\
\ READY..., the digit, and the verdict (GREAT! / WRONG!) are rendered
\ as 4x4 attribute-cell blocks via lib/big-text.fs — each glyph pixel
\ becomes a 4x4 patch of actual pixels, so a single character is 32x32
\ pixels.  Each cell carries its own ink-and-paper attribute, with the
\ pixel layer drawn so that cell-quadrants light up to form the glyph.
\ Reaction stats sit in normal-sized text below.

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

5   constant stats-row

variable total-ms
variable round-count


\ Picking a challenge
\ ──────────────────

:: digit>char    ( n -- c )           48 + ;

: pick-digit    ( -- 0..9 )          digit-count random ;
: random-delay  ( -- frames )        max-delay min-delay - random min-delay + ;


\ Painting big colour text
\ ────────────────────────
\ Each cell carries one attribute byte (ink + paper, bright on); the
\ pixel layer drawn by big-emit decides which 4x4 quadrants show the
\ ink colour and which show the paper.  Paper stays white so the cell
\ blends with the cls background where there's no glyph.

: paint-with    ( ink -- )           paper-white colour big-colours ;

: show-ready    ( -- )
    paper-yellow paint-with
    s" READY..." 0 0 big-type ;

: show-digit    ( n -- )
    paper-cyan paint-with
    digit>char 0 0 big-emit ;

: show-great    ( -- )
    paper-green paint-with
    s" GREAT!" 0 0 big-type ;

: show-wrong    ( -- )
    paper-red paint-with
    s" WRONG!" 0 0 big-type ;

: show-verdict  ( correct? -- )      if show-great else show-wrong then ;


\ Waiting for the player
\ ──────────────────────

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
