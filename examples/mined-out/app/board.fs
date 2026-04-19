\ app/board.fs — tiles, glyphs, shadow grid, fence and mine placement.

require core.fs
require screen.fs
require grid.fs
require rand.fs

32 constant board-cols
22 constant board-rows

15 constant gap-left
16 constant gap-right
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col

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

create board-buf  704 allot

: board-init     ( -- )
    board-buf board-cols board-rows grid-set!
    t-empty grid-clear ;

: tile!          ( tag col row -- )   grid! ;
: tile@          ( col row -- tag )   grid@ ;
: empty?         ( col row -- flag )  tile@ t-empty = ;
: fence?         ( col row -- flag )  tile@ t-fence = ;
: mine?          ( col row -- flag )  tile@ t-mine  = ;
: damsel?        ( col row -- flag )  tile@ t-damsel = ;

: put-char       ( ch col row -- )    at-xy emit ;
: erase-at       ( col row -- )       ch-space    -rot put-char ;
: fence-at       ( col row -- )       ch-fence    -rot put-char ;
: mine-at        ( col row -- )       ch-mine     -rot put-char ;
: player-at      ( col row -- )       ch-player   -rot put-char ;
: damsel-at      ( col row -- )       ch-damsel   -rot put-char ;
: spreader-at    ( col row -- )       ch-spreader -rot put-char ;
: bug-at         ( col row -- )       ch-bug      -rot put-char ;

: gap?           ( col -- flag )      dup gap-left = swap gap-right = or ;

variable _fr

: place-fence-at-col  ( col -- )
    dup gap? 0= if
        dup _fr @ t-fence -rot tile!
        dup _fr @ fence-at
    then drop ;

: fence-row      ( row -- )
    _fr !
    board-cols 0 do i place-fence-at-col loop ;

: build-fences   ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row ;

: rand-col       ( -- col )   board-cols random ;
: rand-interior  ( -- row )   18 random 2 + ;

: try-place-mine ( col row -- )
    2dup empty? if t-mine -rot tile! else 2drop then ;

: scatter-mines  ( n -- )
    0 do rand-col rand-interior try-place-mine loop ;

variable _mr

: reveal-row     ( row -- )
    _mr !
    board-cols 0 do
        i _mr @ mine? if i _mr @ mine-at then
    loop ;

: show-all-mines ( -- )
    board-rows 0 do i reveal-row loop ;
