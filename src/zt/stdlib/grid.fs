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

\ bind the grid to addr with the given width and height
: grid-set!   ( addr w h -- )   grid-h ! grid-w ! grid-addr ! ;
\ total number of cells in the bound grid
: grid-area   ( -- n )          grid-w @ grid-h @ * ;
\ linear cell offset for column col, row row
: grid-idx    ( col row -- off ) grid-w @ * + ;
\ address of the cell at column col, row row
: grid-cell   ( col row -- addr ) grid-idx grid-addr @ + ;
\ fetch the byte at column col, row row
: grid@       ( col row -- v )  grid-cell c@ ;
\ store byte v at column col, row row
: grid!       ( v col row -- )  grid-cell c! ;
\ fill every cell of the grid with byte
: grid-clear  ( byte -- )       grid-addr @ grid-area rot fill ;

\ address of the first cell in row
: grid-row-addr  ( row -- addr )  grid-w @ * grid-addr @ + ;
\ fill every cell in row with byte
: fill-row       ( byte row -- )  grid-row-addr grid-w @ rot fill ;
\ fill every cell in column col with byte
: fill-col       ( byte col -- )
    grid-h @ 0 do  over over i grid!  loop  2drop ;

\ true if n is greater than or equal to zero
: non-neg?    ( n -- flag )    0< invert ;
\ true if row is in [0, grid-h)
: row-ok?     ( row -- flag )  dup grid-h @ < swap non-neg? and ;
\ true if col is in [0, grid-w)
: col-ok?     ( col -- flag )  dup grid-w @ < swap non-neg? and ;
\ true if (col, row) is inside the grid
: in-bounds?  ( col row -- flag )  row-ok? swap col-ok? and ;

variable _ncol
variable _nrow

\ value of the cell offset (dx, dy) from the saved (_ncol, _nrow)
: cell-at     ( dx dy -- v )
    _nrow @ + swap _ncol @ + swap grid@ ;

\ map any nonzero cell value to 1, zero to 0
: cell-bit    ( v -- 0|1 )     0= 0= 1 and ;

\ remember (col, row) as the centre for upcoming cell-at lookups
: save-xy     ( col row -- )   _nrow ! _ncol ! ;

\ count nonzero orthogonal neighbours of (col, row)
: neighbours4  ( col row -- n )
    save-xy
    -1  0 cell-at cell-bit
     1  0 cell-at cell-bit +
     0 -1 cell-at cell-bit +
     0  1 cell-at cell-bit + ;

\ count nonzero neighbours of (col, row) including diagonals
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
