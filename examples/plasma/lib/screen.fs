\ Spectrum attribute-memory helpers.
\ Relative REQUIRE resolves against THIS file's directory.

require math.fs

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

: attr-addr  ( col row -- addr )  scr-cols * + attrs + ;
: attr!      ( attr col row -- )  attr-addr c! ;
