\ Render text by colouring 8x8 attribute-cell blocks.  Each font pixel
\ becomes one whole attribute cell, so a single character occupies an
\ 8x8 grid of cells.  The pixel layer is left blank — paper colour
\ alone shapes each glyph, so letters are "painted" via attributes.

require core.fs
require screen.fs

$3D00 constant rom-font
8     constant glyph-rows
8     constant glyph-cols
8     constant big-cell-size

variable big-on-attr
variable big-off-attr
variable big-col
variable big-row
variable big-cell-row
variable big-type-col
variable big-type-row


: glyph-addr      ( c -- addr )      32 - glyph-rows * rom-font + ;
: glyph-line@     ( c r -- byte )    swap glyph-addr + c@ ;

: bit-on?         ( byte i -- flag ) 7 swap - 1 swap lshift and ;
: pixel-attr      ( flag -- attr )   if big-on-attr @ else big-off-attr @ then ;

: big-colours     ( on off -- )      big-off-attr ! big-on-attr ! ;


: paint-pixel     ( byte i -- )
    2dup bit-on? pixel-attr          ( byte i attr )
    swap big-col @ +                 ( byte attr cell-col )
    big-cell-row @                   ( byte attr cell-col cell-row )
    attr!  drop ;

: paint-glyph-row ( byte row -- )
    big-row @ +  big-cell-row !
    glyph-cols 0 do  dup i paint-pixel  loop
    drop ;

: big-emit        ( c col row -- )
    big-row !  big-col !
    glyph-rows 0 do
        dup i glyph-line@  i paint-glyph-row
    loop
    drop ;


: char-cell-col   ( i -- col )       big-cell-size * big-type-col @ + ;

: big-type        ( addr len col row -- )
    big-type-row !  big-type-col !
    0 do
        dup i + c@                   ( addr c )
        i char-cell-col              ( addr c cell-col )
        big-type-row @               ( addr c cell-col cell-row )
        big-emit
    loop
    drop ;
