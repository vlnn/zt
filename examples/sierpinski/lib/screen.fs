\ Spectrum attribute-memory helpers.
\ Demonstrates relative REQUIRE: this path is resolved against THIS file's
\ directory, so it finds ./math.fs (not lib/lib/math.fs).

require math.fs

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

\ address of the attribute byte at column col, row row
: attr-addr  ( col row -- addr )  scr-cols * + attrs + ;
\ store attr at column col, row row of the attribute area
: attr!      ( attr col row -- )  attr-addr c! ;
