\ stdlib/screen.fs — attribute-area and cursor helpers.
\
\ Assumes zt's custom EMIT (writes through _emit_cursor_row/col).
\ Colour byte layout (Spectrum):
\   bits 0-2: ink    3-5: paper    6: bright    7: flash

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

\ address of the attribute byte at column col, row row
: attr-addr   ( col row -- addr )   scr-cols * + attrs + ;
\ store byte as the attribute at column col, row row
: attr!       ( byte col row -- )   attr-addr c! ;
\ fetch the attribute byte at column col, row row
: attr@       ( col row -- byte )   attr-addr c@ ;

\ pack ink and paper indices into a single attribute byte
: colour      ( ink paper -- byte ) 3 lshift or ;
\ set the bright bit on an attribute byte
: bright      ( byte -- byte' )     64 or ;
\ set the flash bit on an attribute byte
: flashing    ( byte -- byte' )     128 or ;
\ fill the entire 24x32 attribute area with one byte
: fill-attrs  ( byte -- )           attrs 768 rot fill ;

\ fill the 32 attribute bytes of one row with a single colour byte
: row-attrs!  ( byte row -- )
    scr-cols * attrs +  scr-cols  rot fill ;
