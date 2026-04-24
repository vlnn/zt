\ examples/bank-table/main.fs
\
\ M4b demo: declarative `in-bank` CREATE places data tables directly in
\ named RAM banks at compile time, so no runtime seeding loop is needed.
\
\ Compare with examples/bank-rotator/main.fs, which populates banks at
\ runtime via BANK! + C!. This version does the same visible effect but
\ with compile-time bank placement — tables just live where they belong.
\
\ Each table is a single byte; with `in-bank` you can build larger
\ structures (sprite data, level maps, lookup tables) the same way.
\
\ Note: no `128k?` detection here. The detection probe is destructive and
\ would overwrite the compile-time data in banks 0 and 1. For demos that
\ need both compile-time data AND detection, call 128k? first and only
\ then page in the populated banks. This example assumes 128K mode.

0 in-bank create color-0 $46 c, end-bank
1 in-bank create color-1 $4A c, end-bank
3 in-bank create color-3 $52 c, end-bank
4 in-bank create color-4 $61 c, end-bank

: show-bank-at-col  ( bank col -- )
    swap bank!           ( col )
    $C000 c@             ( col attr-byte )
    swap $5800 + c! ;    \ attrs[col] = attr-byte

: cycle  ( -- )
    0 0 show-bank-at-col
    1 1 show-bank-at-col
    3 2 show-bank-at-col
    4 3 show-bank-at-col ;

: main
    7 0 cls
    begin cycle again ;
