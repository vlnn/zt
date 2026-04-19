\ stdlib/screen.fs — attribute-area and cursor helpers.
\
\ Assumes zt's custom EMIT (writes through _emit_cursor_row/col).
\ Colour byte layout (Spectrum):
\   bits 0-2: ink    3-5: paper    6: bright    7: flash

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

: attr-addr   ( col row -- addr )   scr-cols * + attrs + ;
: attr!       ( byte col row -- )   attr-addr c! ;
: attr@       ( col row -- byte )   attr-addr c@ ;

: colour      ( ink paper -- byte ) 3 lshift or ;
: bright      ( byte -- byte' )     64 or ;
: flashing    ( byte -- byte' )     128 or ;
: fill-attrs  ( byte -- )           attrs 768 rot fill ;

: row-attrs!  ( byte row -- )
    scr-cols * attrs +  scr-cols  rot fill ;
