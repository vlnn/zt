\ Top-level game flow: init level, single-frame step, run-loop until dead.
\
\ Frame ordering. game-step renders at the start of the frame (right after
\ wait-frame, while the beam is in the top border) and runs physics at the
\ end. This wins twice: the visible image is finalised before the beam
\ reaches it (no flicker), and physics has the rest of the frame budget
\ in which to run with no rendering deadline.
\
\ Cell restoration. The ball's blit covers a 16x8-pixel window which
\ overlaps up to four character cells (two if y is cell-aligned). We do
\ not call a pixel-level erase; instead, before painting, we restore each
\ overlapped cell to its background — a brick if one lives there, blank
\ otherwise. This means the ball can fly through the brick area without
\ permanently scrubbing brick pixels off the screen.

require core.fs
require screen.fs
require sprites.fs
require bricks.fs
require paddle.fs
require ball.fs
require score.fs

variable hud-counter

48 constant ascii-zero

: emit-digit         ( d -- )    ascii-zero + emit ;
: emit-2digits       ( n -- )
    dup 100 mod 10 / emit-digit
    10 mod emit-digit ;
: emit-3digits       ( n -- )
    dup 1000 mod 100 / emit-digit
    dup 100  mod 10  / emit-digit
    10 mod emit-digit ;

\ HUD digits are printed by jumping the cursor past the static labels
\ ("SCORE " ends at column 7, "LIVES " at column 26) and emitting only
\ the digits. The labels themselves are drawn once at game start.
: hud-print-score    ( -- )
    7 0 at-xy
    score @ emit-3digits ;

: hud-print-lives    ( -- )
    26 0 at-xy
    lives @ emit-digit ;

: hud-print-labels   ( -- )
    1  0 at-xy ." SCORE "
    20 0 at-xy ." LIVES " ;

: draw-hud           ( -- )
    hud-print-score
    hud-print-lives
    hud-clean! ;

: maybe-draw-hud     ( -- )
    hud-dirty @ if draw-hud then ;

: paint-background   ( -- )    0 7 cls ;
: hud-attr           ( -- )    $47 0 row-attrs! ;

$47 constant wall-attr
1   constant wall-top-row
22  constant wall-bottom-row
31  constant wall-right-col

: draw-wall-cell     ( col row -- )
    wall-tile wall-attr 2swap blit8c ;

: draw-blank-cell    ( col row -- )
    brick-blank background-attr 2swap blit8c ;

: cell-is-wall?      ( col -- flag )
    dup 0 = swap wall-right-col = or ;

: draw-wall-column   ( col -- )
    wall-bottom-row 1+ wall-top-row do
        dup i draw-wall-cell
    loop drop ;

: draw-walls         ( -- )
    0 draw-wall-column
    wall-right-col draw-wall-column ;

: pix->cell          ( px -- cell )    2/ 2/ 2/ ;

\ ball-moved? compares raw pixel coordinates, not cell indices. The
\ blit's 16x8-pixel footprint shifts within a cell as the sub-pixel x or y
\ offset changes, so a cell-only check would skip restore in cases where
\ part of the previous frame's ball is still on screen, leaving a trail.
: ball-moved?        ( -- flag )
    ball-x @ ball-ox @ <>
    ball-y @ ball-oy @ <>
    or ;

\ For a cell in the brick rows, restore-brick-cell repaints either the
\ live brick or a blank cell. For a cell outside the brick rows, the
\ caller (ball-restore-cell) shortcuts to draw-blank-cell directly.
: restore-brick-cell ( col row -- )
    over cell->bcol over cell->brow
    2dup brick-alive? if
        2swap 2drop draw-brick
    else
        2drop draw-blank-cell
    then ;

: ball-restore-cell  ( col row -- )
    dup cell-in-brick-rows?  0= if  draw-blank-cell  exit  then
    restore-brick-cell ;

: ball-y-aligned?    ( -- flag )    ball-oy @ 7 and 0= ;

\ Smart restore: blit8x writes 8 vertical pixel rows starting at ball-oy.
\ When ball-oy is cell-aligned (y mod 8 = 0) those 8 rows live in a
\ single character row, so restoring the second row would scrub cells
\ the ball never actually painted (notably the paddle row when the ball
\ is at y=168). When misaligned, the footprint spans two rows and we
\ restore all four cells.
: restore-old-cells  ( -- )
    ball-ox @ pix->cell  ball-oy @ pix->cell
    2dup            ball-restore-cell
    over 1+ over    ball-restore-cell
    ball-y-aligned? if 2drop exit then
    over over 1+    ball-restore-cell
    swap 1+ swap 1+ ball-restore-cell ;

: restore-ball-bg    ( -- )
    ball-moved? if restore-old-cells then ;

: init-level         ( -- )
    bricks-bind
    bricks-fill-alive
    draw-walls
    draw-all-bricks
    paddle-reset
    ball-reset
    draw-paddle
    draw-ball
    ball-save-pos
    mark-hud-dirty
    draw-hud ;

: handle-ball-lost   ( -- )
    ball-lost @ 0= if exit then
    restore-old-cells
    lose-life
    ball-reset
    ball-save-pos ;

: handle-cleared     ( -- )
    bricks-alive 0= if
        restore-old-cells
        bricks-fill-alive
        draw-all-bricks
        ball-reset
        ball-save-pos
    then ;

\ Per-frame body. wait-frame holds until vblank; the rendering work
\ (restore + paint + paddle) happens during the top border, then
\ physics runs while the visible scan is in progress.
: game-step          ( -- )
    wait-frame
    restore-ball-bg
    ball-paint
    paddle-step
    ball-physics
    handle-ball-lost
    handle-cleared
    maybe-draw-hud ;

: game-loop          ( -- )
    begin
        game-step
        dead?
    until ;

\ arkanoid is the entry point. Order matters: paint-background clears
\ the whole screen, hud-attr fixes the colour of row 0, hud-print-labels
\ prints the static "SCORE" / "LIVES" text once, scoring-reset zeros the
\ counters, lock-sprites disables interrupts so blit8x can run safely,
\ and finally init-level lays out the playfield.
: arkanoid           ( -- )
    paint-background
    hud-attr
    hud-print-labels
    scoring-reset
    lock-sprites
    init-level
    game-loop ;
