\ Render text into 4x4 attribute-cell blocks, with both pixels and
\ attributes — each cell covers a 2x2 group of glyph pixels and shows
\ that pattern as four 4x4-pixel quadrants (TL, TR, BL, BR).
\
\ Within one cell every cell-row of pixels in the top half is the
\ same byte (TL/TR-derived) and the bottom half another (BL/BR), so
\ the cell only has 4 possible byte shapes: $00 (both off), $0F
\ (right pixel on), $F0 (left on), $FF (both on).  We keep them in
\ a 4-entry lookup table indexed by the 2-bit (left, right) pair.

require core.fs
require screen.fs

$3D00 constant rom-font
$4000 constant pix-base
8     constant glyph-rows
8     constant glyph-cols
4     constant big-cell-size
4     constant cells-per-side

create half-row-byte  $00 c, $0F c, $F0 c, $FF c,

variable big-attr
variable big-col
variable big-row
variable big-shift
variable cell-top
variable cell-bot
variable big-type-col
variable big-type-row


: glyph-addr     ( c -- addr )       32 - glyph-rows * rom-font + ;
: glyph-line@    ( c r -- byte )     swap glyph-addr + c@ ;

: bit-on?        ( byte i -- flag )  7 swap - 1 swap lshift and ;

: merge-glyph    ( c -- byte )
    0 glyph-rows 0 do  over i glyph-line@ or  loop  nip ;

: leading-blanks ( c -- n )
    merge-glyph
    glyph-cols 0 do
        dup i bit-on? if  drop i unloop exit  then
    loop
    drop glyph-cols ;


: big-colours    ( attr -- )         big-attr ! ;

: cell-pix-addr  ( col row -- addr )
    dup 8 /  11 lshift                    ( col row band<<11 )
    swap 7 and  5 lshift  or              ( col combined )
    swap or  pix-base or ;

: cell-bits      ( byte cc -- bits )
    2 *  6 swap -  rshift  3 and ;

: half-byte      ( bits -- byte )    half-row-byte + c@ ;

: trimmed-row    ( c r -- byte )
    glyph-line@  big-shift @ lshift  $FF and ;


: fill-pixel-rows ( byte addr count -- )
    0 do  2dup c!  256 +  loop
    2drop ;

: paint-cell      ( col row -- )
    2dup big-attr @ -rot attr!            ( col row )
    cell-pix-addr                         ( base )
    dup cell-top @ swap 4 fill-pixel-rows
    1024 +
    cell-bot @ swap 4 fill-pixel-rows ;

: prep-halves     ( c cc cr -- )
    >r                                        ( c cc,         R: cr )
    over r@ 2 *  trimmed-row                  ( c cc top,     R: cr )
    over cell-bits half-byte cell-top !       ( c cc,         R: cr )
    over r> 2 * 1+  trimmed-row               ( c cc bot )
    swap cell-bits half-byte cell-bot !       ( c )
    drop ;

: render-char     ( c -- )
    cells-per-side 0 do
        cells-per-side 0 do
            dup i j prep-halves
            big-col @ i +
            big-row @ j +
            paint-cell
        loop
    loop
    drop ;

: big-emit        ( c col row -- )
    big-row !  big-col !
    dup leading-blanks big-shift !
    render-char ;


: char-cell-col   ( i -- col )       big-cell-size *  big-type-col @ + ;

: big-type        ( addr len col row -- )
    big-type-row !  big-type-col !
    0 do
        dup i + c@                        ( addr c )
        i char-cell-col                   ( addr c cell-col )
        big-type-row @                    ( addr c cell-col cell-row )
        big-emit
    loop
    drop ;
