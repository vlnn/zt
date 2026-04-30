\ Top-level game flow: init level, single-frame step, run-loop until dead.

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

: hud-print-score    ( -- )
    1 0 at-xy
    ." SCORE "
    score @ emit-3digits ;

: hud-print-lives    ( -- )
    20 0 at-xy
    ." LIVES "
    lives @ emit-digit ;

: draw-hud           ( -- )
    hud-print-score
    hud-print-lives
    hud-clean! ;

: maybe-draw-hud     ( -- )
    hud-dirty @ if draw-hud then ;

: paint-background   ( -- )    7 0 cls ;
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

: restore-brick-cell ( col row -- )
    over cell->bcol over cell->brow
    2dup brick-alive? if
        2swap 2drop draw-brick
    else
        2drop draw-blank-cell
    then ;

: restore-cell-bg    ( col row -- )
    over cell-is-wall?           if  draw-wall-cell    exit  then
    dup cell-in-brick-rows?  0= if  draw-blank-cell   exit  then
    restore-brick-cell ;

: restore-ball-bg    ( -- )
    ball-ox @ pix->cell  ball-oy @ pix->cell
    2dup            restore-cell-bg
    over 1+ over    restore-cell-bg
    over over 1+    restore-cell-bg
    swap 1+ swap 1+ restore-cell-bg ;

: init-level         ( -- )
    bricks-bind
    bricks-fill-alive
    draw-walls
    draw-all-bricks
    paddle-reset
    ball-reset
    draw-paddle
    draw-ball
    mark-hud-dirty
    draw-hud ;

: handle-ball-lost   ( -- )
    ball-lost @ 0= if exit then
    restore-ball-bg
    lose-life
    ball-reset ;

: handle-cleared     ( -- )
    bricks-alive 0= if
        restore-ball-bg
        bricks-fill-alive
        draw-all-bricks
        ball-reset
    then ;

: game-step          ( -- )
    restore-ball-bg
    paddle-step
    ball-step
    handle-ball-lost
    handle-cleared
    maybe-draw-hud
    wait-frame ;

: game-loop          ( -- )
    begin
        game-step
        dead?
    until ;

: arkanoid           ( -- )
    paint-background
    hud-attr
    scoring-reset
    lock-sprites
    init-level
    wait-frame
    game-loop ;
