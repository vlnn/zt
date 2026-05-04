\ Top-level game flow: HUD, walls, cell-level background restoration,
\ level init, and the per-frame loop that runs everything.  The big
\ design idea is that physics writes through to the cell-restore
\ system instead of doing pixel-level erase, so the ball can fly
\ through the brick area without scrubbing brick pixels off-screen.
\
\ Frame timing.  game-step renders at the start of the frame (right
\ after wait-frame, while the beam is in the top border) and runs
\ physics at the end.  Two wins: the visible image is finalised
\ before the beam reaches it (no flicker), and physics has the rest
\ of the frame budget to run without a render deadline.

require core.fs
require screen.fs
require sprites.fs
require bricks.fs
require paddle.fs
require ball.fs
require score.fs


\ Number printing
\ ───────────────
\ Three small helpers used by the HUD only.  They emit fixed-width
\ digit strings so the score doesn't ripple horizontally as it grows.

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


\ The HUD
\ ───────
\ The static labels ("SCORE ", "LIVES ") are drawn once at game start
\ and never repainted; the digits update by jumping the cursor past
\ each label and emitting the new value.  maybe-draw-hud is the cheap
\ check called every frame — it skips the work unless score.fs has
\ marked the HUD dirty.

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


\ Walls and background
\ ────────────────────
\ The play area is bounded on the left and right by columns of solid
\ blocks, drawn once at level init.  paint-background clears the
\ screen; hud-attr fixes row 0's colour so the score text stands out.

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


\ Cell-level ball erase
\ ─────────────────────
\ The ball's blit covers a 16x8-pixel window — up to four character
\ cells (two when y is cell-aligned).  Instead of pixel-level erase,
\ we restore each overlapped cell to whatever should be there: a
\ live brick if one exists at those coordinates, or blank otherwise.
\ ball-moved? compares raw pixel coordinates, not cells, because
\ within a single cell the sub-pixel offset still moves the visible
\ footprint, and a cell-only check would skip restore in those cases
\ and leave a trail.

: pix->cell          ( px -- cell )    2/ 2/ 2/ ;

: ball-moved?        ( -- flag )
    ball-x @ ball-ox @ <>
    ball-y @ ball-oy @ <>
    or ;

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


\ Cell-restore footprint
\ ──────────────────────
\ blit8x writes 8 vertical pixel rows starting at ball-oy.  When
\ ball-oy is cell-aligned (y mod 8 = 0) those 8 rows live in a single
\ character row, so restoring the second row would scrub cells the
\ ball never actually painted — notably the paddle row when the ball
\ is at y = 168.  When misaligned, the footprint spans two cell rows
\ and we restore all four cells.

: restore-old-cells  ( -- )
    ball-ox @ pix->cell  ball-oy @ pix->cell
    2dup            ball-restore-cell
    over 1+ over    ball-restore-cell
    ball-y-aligned? if 2drop exit then
    over over 1+    ball-restore-cell
    swap 1+ swap 1+ ball-restore-cell ;

: restore-ball-bg    ( -- )
    ball-moved? if restore-old-cells then ;


\ Level setup and end-of-level handling
\ ─────────────────────────────────────
\ init-level paints the wall, fills and draws the brick grid, and
\ resets the paddle and ball to their starting positions.
\ handle-ball-lost is the one-life-down branch; handle-cleared
\ refills the brick wall when it's empty so the game continues.

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


\ Per-frame loop and entry
\ ────────────────────────
\ game-step waits for vblank, restores the ball's old footprint,
\ paints the new ball, runs paddle input and ball physics, handles
\ life loss or level clear, and finally repaints the HUD if dirty.
\ arkanoid is the entry point — order matters: clear, fix HUD attr,
\ draw labels, zero counters, lock sprites (disable interrupts so
\ blit8x is safe), then init-level + game-loop.

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

: arkanoid           ( -- )
    paint-background
    hud-attr
    hud-print-labels
    scoring-reset
    lock-sprites
    init-level
    game-loop ;
