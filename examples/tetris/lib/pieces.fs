\ The seven tetrominoes.  Each piece has 4 rotations stored as 4 rows
\ of 4 cells, packed into the low nibble of one byte per row (bit 3 =
\ leftmost cell).  Piece layout: 7 pieces * 4 rotations * 4 rows = 112
\ bytes.  Index of a row: piece*16 + rot*4 + row.

require core.fs

7 constant piece-count
4 constant piece-rotations
4 constant piece-rows
4 constant piece-cols

0 constant piece-i
1 constant piece-o
2 constant piece-t
3 constant piece-s
4 constant piece-z
5 constant piece-l
6 constant piece-j

create piece-shapes
    \ I — cyan
    $0 c, $F c, $0 c, $0 c,
    $4 c, $4 c, $4 c, $4 c,
    $0 c, $F c, $0 c, $0 c,
    $4 c, $4 c, $4 c, $4 c,
    \ O — yellow
    $6 c, $6 c, $0 c, $0 c,
    $6 c, $6 c, $0 c, $0 c,
    $6 c, $6 c, $0 c, $0 c,
    $6 c, $6 c, $0 c, $0 c,
    \ T — magenta
    $4 c, $E c, $0 c, $0 c,
    $4 c, $6 c, $4 c, $0 c,
    $0 c, $E c, $4 c, $0 c,
    $4 c, $C c, $4 c, $0 c,
    \ S — green
    $6 c, $C c, $0 c, $0 c,
    $4 c, $6 c, $2 c, $0 c,
    $6 c, $C c, $0 c, $0 c,
    $4 c, $6 c, $2 c, $0 c,
    \ Z — red
    $C c, $6 c, $0 c, $0 c,
    $2 c, $6 c, $4 c, $0 c,
    $C c, $6 c, $0 c, $0 c,
    $2 c, $6 c, $4 c, $0 c,
    \ L — white
    $2 c, $E c, $0 c, $0 c,
    $4 c, $4 c, $6 c, $0 c,
    $0 c, $E c, $8 c, $0 c,
    $C c, $4 c, $4 c, $0 c,
    \ J — blue
    $8 c, $E c, $0 c, $0 c,
    $6 c, $4 c, $4 c, $0 c,
    $0 c, $E c, $2 c, $0 c,
    $4 c, $4 c, $C c, $0 c,

\ Per-piece attribute byte (bright + ink).  Used both for drawing the
\ live piece and for staining the playfield cells once it locks down.

$45 constant attr-i
$46 constant attr-o
$43 constant attr-t
$44 constant attr-s
$42 constant attr-z
$47 constant attr-l
$41 constant attr-j

create piece-attrs
    attr-i c, attr-o c, attr-t c,
    attr-s c, attr-z c, attr-l c, attr-j c,

\ Row offset within the table: piece*16 + rotation*4.

: piece-row-base   ( piece rot -- off )
    swap 16 *  swap 4 * + ;

: piece-row        ( piece rot row -- bits )
    >r piece-row-base r> + piece-shapes + c@ ;

: piece-attr       ( piece -- attr )
    piece-attrs + c@ ;

\ Test a single cell of a piece: returns true (-1) if filled, 0 empty.
\ Bit 3 = leftmost (col 0); shift down by (3 - col) and mask bit 0.

: piece-cell?      ( piece rot row col -- flag )
    >r piece-row r> 3 swap - rshift 1 and 0= 0= ;
