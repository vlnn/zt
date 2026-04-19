\ Spectrum attribute-memory helpers.
\ Relative REQUIRE resolves against THIS file's directory.

require math.fs

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

: row-addr   ( row -- addr )      5 lshift attrs + ;
: attr-addr  ( col row -- addr )  row-addr + ;
: attr!      ( attr col row -- )  attr-addr c! ;
