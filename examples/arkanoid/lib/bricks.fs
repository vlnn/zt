\ The 30×4 brick grid: layout, drawing, hit detection, and the
\ coordinate translations that bridge brick-grid space, screen-cell
\ space, and pixel space.

require core.fs
require grid.fs
require screen.fs
require sprites.fs
require array.fs


\ Layout and state
\ ────────────────
\ Brick column 0..29 maps to screen char column 1..30; columns 0 and
\ 31 are reserved for the side walls.  Brick row 0..3 maps to screen
\ rows 2..5.  brick-grid is the live/dead bitmap (one byte per brick,
\ via grid.fs); brick-count caches the live total so handle-cleared
\ in game.fs can detect a clear in O(1) instead of scanning the grid.
\ row-attrs gives each row its own colour.

30 constant bricks-cols
4  constant bricks-rows
2  constant bricks-row-base
1  constant bricks-col-base
$07 constant background-attr

create brick-grid 120 allot
c: row-attrs   $42 c, $46 c, $44 c, $45 c, ;

variable brick-count

: bricks-bind        ( -- )    brick-grid bricks-cols bricks-rows grid-set! ;
: total-bricks       ( -- n )    bricks-cols bricks-rows * ;
: bricks-fill-alive  ( -- )    1 grid-clear total-bricks brick-count ! ;
: bricks-alive       ( -- n )    brick-count @ ;
: row-attr           ( brow -- attr )   row-attrs swap a-byte@ ;
: bricks-screen-row  ( brow -- row )    bricks-row-base + ;
: bricks-screen-col  ( bcol -- col )    bricks-col-base + ;
: brick-alive?       ( bcol brow -- flag )   grid@ 0= 0= ;
: brick-clear        ( bcol brow -- )   0 -rot grid! ;


\ Drawing
\ ───────
\ One blit8c per brick, with the row's pre-set colour.  draw-bricks-row
\ paints a whole row of 30; draw-all-bricks runs it for the four rows.
\ erase-brick uses brick-blank with the background attribute, so an
\ erased cell visually matches the gap above the bricks.

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


\ Coordinate translations
\ ───────────────────────
\ Three coordinate systems coexist: pixels (0..255 horizontally),
\ screen cells (0..31 / 0..23), and brick coordinates (0..29 / 0..3).
\ The `pixel->b*` words divide by 8 — implemented as `2/ 2/ 2/`
\ because zt has no native divide — and shift the origin into brick
\ space.  ball-center-* finds the centre of an 8x8 sprite.

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


\ Hit detection
\ ─────────────
\ hit-cell is the all-or-nothing brick-collision primitive: if a live
\ brick exists at (bcol, brow), erase it, decrement the live count,
\ and return true; otherwise leave everything unchanged and return
\ false.  ball-hits-brick? samples a single point — the ball's
\ centre — against the grid; corner-clipping registers as a hit only
\ when the centre crosses the brick boundary.

: hit-cell           ( bcol brow -- hit? )
    2dup brick-in-range? 0= if 2drop 0 exit then
    2dup brick-alive?    0= if 2drop 0 exit then
    2dup erase-brick
    2dup brick-clear
    -1 brick-count +!
    2drop
    -1 ;

: ball-hits-brick?   ( bx by -- hit? )
    ball-center-y pixel->brow
    swap ball-center-x pixel->bcol
    swap hit-cell ;
