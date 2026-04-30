\ Brick grid for arkanoid.
\
\ A brick lives in a fixed 30x4 grid. Brick column 0..29 maps to screen
\ char column 1..30 — char columns 0 and 31 are reserved for side walls.
\ Brick row 0..3 maps to screen char row 2..5.
\
\ Two coordinate systems coexist:
\   - brick coords (bcol, brow) — index into the 30x4 grid
\   - cell coords (col, row)    — screen character cell
\ Words with `cell->` prefix translate from screen cells to brick coords.
\ brick-count caches the live-brick total so handle-cleared can detect
\ a cleared level in O(1) instead of scanning the grid each frame.

require core.fs
require grid.fs
require screen.fs
require sprites.fs

30 constant bricks-cols
4  constant bricks-rows
2  constant bricks-row-base
1  constant bricks-col-base
$07 constant background-attr

create brick-grid 120 allot
\ One paper/ink byte per brick row (0..3), giving each row a colour.
create row-attrs   $42 c, $46 c, $44 c, $45 c,

variable brick-count

: bricks-bind        ( -- )    brick-grid bricks-cols bricks-rows grid-set! ;
: total-bricks       ( -- n )    bricks-cols bricks-rows * ;
: bricks-fill-alive  ( -- )    1 grid-clear total-bricks brick-count ! ;
: bricks-alive       ( -- n )    brick-count @ ;
: row-attr           ( brow -- attr )   row-attrs + c@ ;
: bricks-screen-row  ( brow -- row )    bricks-row-base + ;
: bricks-screen-col  ( bcol -- col )    bricks-col-base + ;
: brick-alive?       ( bcol brow -- flag )   grid@ 0= 0= ;
: brick-clear        ( bcol brow -- )   0 -rot grid! ;

: draw-brick         ( bcol brow -- )
    >r
    brick-tile
    r@ row-attr
    rot bricks-screen-col
    r> bricks-screen-row
    blit8c ;

: erase-brick        ( bcol brow -- )
    >r
    brick-blank
    background-attr
    rot bricks-screen-col
    r> bricks-screen-row
    blit8c ;

: draw-bricks-row    ( brow -- )
    bricks-cols 0 do
        i over draw-brick
    loop drop ;

: draw-all-bricks    ( -- )
    bricks-rows 0 do i draw-bricks-row loop ;

\ Convert pixel coordinates to brick coordinates. `2/ 2/ 2/` is `/8`
\ implemented as three signed shifts since zt has no native divide.
: ball-center-x      ( bx -- cx )      4 + ;
: ball-center-y      ( by -- cy )      4 + ;
: pixel->bcol        ( px -- bcol )    2/ 2/ 2/ bricks-col-base - ;
: pixel->brow        ( py -- brow )    2/ 2/ 2/ bricks-row-base - ;

: cell-in-brick-rows? ( row -- flag )
    dup bricks-row-base < if drop 0 exit then
    bricks-row-base bricks-rows + < ;

: cell->bcol         ( col -- bcol )   bricks-col-base - ;
: cell->brow         ( row -- brow )   bricks-row-base - ;

: bcol-in-range?     ( bcol -- flag )  dup 0 < if drop 0 exit then bricks-cols < ;
: brow-in-range?     ( brow -- flag )  dup 0 < if drop 0 exit then bricks-rows < ;
: brick-in-range?    ( bcol brow -- flag )
    brow-in-range? swap bcol-in-range? and ;

\ hit-cell: if a live brick exists at (bcol, brow), erase it, decrement
\ brick-count, and return -1; otherwise return 0 without side effects.
: hit-cell           ( bcol brow -- hit? )
    2dup brick-in-range? 0= if 2drop 0 exit then
    2dup brick-alive?    0= if 2drop 0 exit then
    2dup erase-brick
    2dup brick-clear
    -1 brick-count +!
    2drop
    -1 ;

\ Sample a single point — the ball's centre — against the brick grid.
\ This is a small approximation: a ball clipping a brick corner only
\ registers a hit when its centre crosses into the brick cell.
: ball-hits-brick?   ( bx by -- hit? )
    ball-center-y pixel->brow
    swap ball-center-x pixel->bcol
    swap hit-cell ;
