include test-lib.fs
include core.fs
include screen.fs
include udg.fs

: test-colour-black-on-white
    0 7 colour  56 assert-eq ;

: test-colour-white-on-black
    7 0 colour  7 assert-eq ;

: test-colour-red-on-yellow
    2 6 colour  50 assert-eq ;

: test-bright-sets-bit-6
    0 bright  64 assert-eq ;

: test-flashing-sets-bit-7
    0 flashing  128 assert-eq ;

: test-bright-flashing-combined
    7 bright flashing  199 assert-eq ;

: test-attr-addr-origin
    0 0 attr-addr  $5800 assert-eq ;

: test-attr-addr-col5
    5 0 attr-addr  $5805 assert-eq ;

: test-attr-addr-row1
    0 1 attr-addr  $5820 assert-eq ;

: test-attr-addr-row23-col31
    31 23 attr-addr  $5AFF assert-eq ;

: test-attr-store-fetch-roundtrip
    42 10 5 attr!
    10 5 attr@  42 assert-eq ;

: test-attr-store-writes-right-address
    42 10 5 attr!
    $5800 32 5 * + 10 + c@  42 assert-eq ;

: test-fill-attrs-writes-origin
    56 fill-attrs
    0 0 attr@  56 assert-eq ;

: test-fill-attrs-writes-last
    56 fill-attrs
    31 23 attr@  56 assert-eq ;

: test-row-attrs-writes-whole-row
    99 10 row-attrs!
    0 10 attr@  99 assert-eq ;

: test-row-attrs-writes-last-col-of-row
    99 10 row-attrs!
    31 10 attr@  99 assert-eq ;

: test-row-attrs-does-not-bleed-to-next
    0 fill-attrs
    99 10 row-attrs!
    0 11 attr@  0 assert-eq ;

: test-at-xy-emit-writes-to-cell
    0 0 cls
    10 5 at-xy
    65 emit
    10 5 screen-base c@  65 assert-eq ;

: test-at-xy-emit-writes-correct-row
    0 0 cls
    0 7 at-xy
    66 emit
    0 7 screen-base c@  66 assert-eq ;

: test-at-xy-preserves-lower-stack
    42 10 5 at-xy
    42 assert-eq ;
