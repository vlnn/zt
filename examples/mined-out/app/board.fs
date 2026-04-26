\ app/board.fs — tiles, glyphs, shadow grid, fence and mine placement.

require core.fs
require screen.fs
require grid.fs
require rand.fs

32 constant board-cols
23 constant board-rows

15 constant gap-left
16 constant gap-right
0  constant left-wall-col
31 constant right-wall-col
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col
22 constant banner-row

0 constant t-empty
1 constant t-mine
2 constant t-fence
3 constant t-damsel

32 constant ch-space
35 constant ch-fence
42 constant ch-mine
79 constant ch-player
63 constant ch-damsel
37 constant ch-spreader
64 constant ch-bug
66 constant ch-bill
126 constant ch-wind

create board-buf  736 allot

\ bind the shadow grid to the board buffer and clear all tiles to empty
: board-init     ( -- )
    board-buf board-cols board-rows grid-set!
    t-empty grid-clear ;

\ store a tile tag at (col, row) of the shadow grid
: tile!          ( tag col row -- )   grid! ;
\ fetch the tile tag at (col, row)
: tile@          ( col row -- tag )   grid@ ;
\ true if the cell at (col, row) is empty
: empty?         ( col row -- flag )  tile@ t-empty = ;
\ true if the cell at (col, row) is a fence
: fence?         ( col row -- flag )  tile@ t-fence = ;
\ true if the cell at (col, row) holds a mine
: mine?          ( col row -- flag )  tile@ t-mine  = ;
\ true if the cell at (col, row) holds a damsel
: damsel?        ( col row -- flag )  tile@ t-damsel = ;

\ emit character ch at screen (col, row)
: put-char       ( ch col row -- )    at-xy emit ;
\ blank the screen cell at (col, row)
: erase-at       ( col row -- )       ch-space    -rot put-char ;
\ draw a fence glyph at (col, row)
: fence-at       ( col row -- )       ch-fence    -rot put-char ;
\ draw a mine glyph at (col, row)
: mine-at        ( col row -- )       ch-mine     -rot put-char ;
\ draw the player glyph at (col, row)
: player-at      ( col row -- )       ch-player   -rot put-char ;
\ draw a damsel glyph at (col, row)
: damsel-at      ( col row -- )       ch-damsel   -rot put-char ;
\ draw the spreader glyph at (col, row)
: spreader-at    ( col row -- )       ch-spreader -rot put-char ;
\ draw the bug glyph at (col, row)
: bug-at         ( col row -- )       ch-bug      -rot put-char ;
\ draw Bill at (col, row)
: bill-at        ( col row -- )       ch-bill     -rot put-char ;

56  constant trail-attr
248 constant wind-attr

\ leave a coloured trail mark on (col, row) where the player has been
: trail-at       ( col row -- )
    2dup erase-at
    trail-attr -rot attr! ;

\ draw a wind gust glyph with its tinted attribute at (col, row)
: wind-at        ( col row -- )
    2dup ch-wind -rot put-char
    wind-attr -rot attr! ;

\ true if col is one of the two top-fence gap columns
: gap?           ( col -- flag )      dup gap-left = swap gap-right = or ;

\ tag (col, row) as a fence cell and draw the fence glyph
: place-fence-cell  ( col row -- )
    2dup t-fence -rot tile!
    fence-at ;

\ tag (col, row) as empty and blank it on screen
: erase-cell        ( col row -- )
    2dup t-empty -rot tile!
    erase-at ;

\ place a fence at (col, row) unless col is the gap
: place-fence-at-col  ( col row -- )
    over gap? if 2drop exit then
    place-fence-cell ;

\ build a horizontal fence at the given row, leaving the gap open
: fence-row      ( row -- )
    board-cols 0 do  i over place-fence-at-col  loop drop ;

\ place left- and right-wall fence cells at the given row
: side-wall-row  ( row -- )
    dup  left-wall-col  swap place-fence-cell
        right-wall-col  swap place-fence-cell ;

\ build the vertical side walls between the top and bottom fences
: build-side-walls  ( -- )
    bottom-fence-row top-fence-row 1+ do i side-wall-row loop ;

\ build the entire enclosing fence: top, bottom, and side walls
: build-fences   ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row
    build-side-walls ;

\ random column 0..board-cols-1
: rand-col       ( -- col )   board-cols random ;
\ random row inside the playfield, avoiding fences and start area
: rand-interior  ( -- row )   18 random 2 + ;

\ place a mine at (col, row) only if the cell is currently empty
: try-place-mine ( col row -- )
    2dup empty? if t-mine -rot tile! else 2drop then ;

\ randomly attempt to place n mines (some attempts may collide and fail)
: scatter-mines  ( n -- )
    0 do rand-col rand-interior try-place-mine loop ;

\ if (col, row) is a mine, draw it on screen
: reveal-cell-if-mine  ( col row -- )
    2dup mine? if mine-at else 2drop then ;

\ if (col, row) is a mine, blank it on screen (leaving the tag intact)
: erase-cell-if-mine   ( col row -- )
    2dup mine? if erase-at else 2drop then ;

\ reveal every mine in the given row
: reveal-row     ( row -- )
    board-cols 0 do  i over reveal-cell-if-mine  loop drop ;

\ reveal every mine on the board (cheat or end-of-level)
: show-all-mines ( -- )
    board-rows 0 do i reveal-row loop ;

\ hide every mine in the given row (visual only)
: hide-mines-in-row  ( row -- )
    board-cols 0 do  i over erase-cell-if-mine  loop drop ;

\ hide every mine on the board (visual only)
: hide-all-mines ( -- )
    board-rows 0 do i hide-mines-in-row loop ;

\ coordinates of the left half of the top-row gap
: top-gap-left-cell   ( -- col row )   gap-left  top-fence-row ;
\ coordinates of the right half of the top-row gap
: top-gap-right-cell  ( -- col row )   gap-right top-fence-row ;

\ true if both gap cells are currently empty
: gap-open?      ( -- flag )
    top-gap-left-cell  empty?
    top-gap-right-cell empty?  and ;

\ close the top-row gap by placing fences in both gap cells
: close-top-gap  ( -- )
    top-gap-left-cell  place-fence-cell
    top-gap-right-cell place-fence-cell ;

\ open the top-row gap by erasing the two gap cells
: open-top-gap   ( -- )
    top-gap-left-cell  erase-cell
    top-gap-right-cell erase-cell ;
