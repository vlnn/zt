\ stdlib/grid.fs — byte-per-cell shadow grid with 4- and 8-connected neighbour counts.
\
\ Usage:
\   create board   704 allot            \ = 32 * 22
\   board 32 22 grid-set!
\   0 grid-clear
\   1 5 3 grid!          \ place a 1 at column 5, row 3
\   4 2 neighbours4 .    \ count nonzero orthogonal neighbours

require core.fs

variable grid-addr
variable grid-w
variable grid-h

: grid-set!   ( addr w h -- )   grid-h ! grid-w ! grid-addr ! ;
: grid-area   ( -- n )          grid-w @ grid-h @ * ;
: grid-idx    ( col row -- off ) grid-w @ * + ;
: grid-cell   ( col row -- addr ) grid-idx grid-addr @ + ;
: grid@       ( col row -- v )  grid-cell c@ ;
: grid!       ( v col row -- )  grid-cell c! ;
: grid-clear  ( byte -- )       grid-addr @ grid-area rot fill ;

: grid-row-addr  ( row -- addr )  grid-w @ * grid-addr @ + ;
: fill-row       ( byte row -- )  grid-row-addr grid-w @ rot fill ;
: fill-col       ( byte col -- )
    grid-h @ 0 do  over over i grid!  loop  2drop ;

: non-neg?    ( n -- flag )    0< invert ;
: row-ok?     ( row -- flag )  dup grid-h @ < swap non-neg? and ;
: col-ok?     ( col -- flag )  dup grid-w @ < swap non-neg? and ;
: in-bounds?  ( col row -- flag )  row-ok? swap col-ok? and ;

variable _ncol
variable _nrow

: cell-at     ( dx dy -- v )
    _nrow @ + swap _ncol @ + swap grid@ ;

: cell-bit    ( v -- 0|1 )     0= 0= 1 and ;

: save-xy     ( col row -- )   _nrow ! _ncol ! ;

: neighbours4  ( col row -- n )
    save-xy
    -1  0 cell-at cell-bit
     1  0 cell-at cell-bit +
     0 -1 cell-at cell-bit +
     0  1 cell-at cell-bit + ;

: neighbours8  ( col row -- n )
    save-xy
    -1 -1 cell-at cell-bit
    -1  0 cell-at cell-bit +
    -1  1 cell-at cell-bit +
     0 -1 cell-at cell-bit +
     0  1 cell-at cell-bit +
     1 -1 cell-at cell-bit +
     1  0 cell-at cell-bit +
     1  1 cell-at cell-bit + ;
