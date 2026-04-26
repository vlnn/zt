\ stdlib/udg.fs — user-defined graphics at $FF58, plus direct cell drawing.
\
\ Each UDG is 8 bytes, one per scanline. Slot 0 maps to CHR$ 144 on a real
\ Spectrum. zt's EMIT uses the ROM font and does NOT dispatch UDG codes,
\ so use `draw-udg` to place a UDG directly at a cell position.
\
\ Usage:
\   create mine-glyph  $00 c, $3C c, $7E c, $DB c, $DB c, $7E c, $3C c, $00 c,
\   mine-glyph 0 udg!
\   0 5 3 draw-udg

$FF58 constant udg-base
8     constant udg-bytes

\ address of the 8-byte UDG slot for index n
: udg-addr    ( n -- addr )   udg-bytes * udg-base + ;
\ character code corresponding to UDG slot n (Spectrum CHR$ 144 onwards)
: udg-char    ( n -- c )      144 + ;
\ copy 8 bytes from src into UDG slot n
: udg!        ( src n -- )    udg-addr udg-bytes cmove ;

\ pixel address of the top-left of the cell at column col, row row
: screen-base  ( col row -- addr )
    dup 7 and 32 *
    swap 3 rshift 2048 *
    + $4000 + + ;

\ pixel address of scanline `line` within the cell at base
: cell-line-addr  ( base line -- addr )  256 * + ;

\ copy 8 source bytes line by line into the 8 scanlines of dst's cell
: copy-8-lines  ( src dst -- )
    8 0 do
        over i + c@
        over i cell-line-addr c!
    loop 2drop ;

\ draw the UDG at index udg-idx into the screen cell at (col, row)
: draw-udg    ( udg-idx col row -- )
    screen-base >r  udg-addr  r>  copy-8-lines ;

\ blank all 8 pixel rows of the cell at (col, row)
: erase-cell  ( col row -- )
    screen-base
    8 0 do  0 over i cell-line-addr c!  loop
    drop ;
