\ Spectrum attribute-memory helpers — addresses inside the 32×24
\ attribute grid at $5800, plus the store primitive.  The relative
\ require below resolves against this file's directory, so `math.fs`
\ finds the sibling in lib/, not lib/lib/.  Both this file and main.fs
\ require math.fs; the resolver dedups so it loads once.

require math.fs

$5800 constant attrs
32    constant scr-cols
24    constant scr-rows

: attr-addr  ( col row -- addr )  scr-cols * + attrs + ;
: attr!      ( attr col row -- )  attr-addr c! ;
