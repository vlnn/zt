\ Spectrum attribute-memory helpers — addresses inside the 32×24
\ attribute grid at $5800, plus the store primitive.  The relative
\ require below resolves against this file's directory, so `math.fs`
\ finds the sibling in lib/.  row-addr exploits the 32-column row
\ stride: `row << 5` is the row offset from `attrs`.

require math.fs

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

: row-addr   ( row -- addr )      5 lshift attrs + ;
: attr-addr  ( col row -- addr )  row-addr + ;
: attr!      ( attr col row -- )  attr-addr c! ;
