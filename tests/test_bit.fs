include test-lib.fs
include bit.fs

create tb-flags  16 allot

: setup-empty       tb-flags 16 8 *  swap bit-erase ;
: setup-all-ones    tb-flags 16 255 fill ;

: test-bytes-zero        0 bit-bytes 0 assert-eq ;
: test-bytes-one         1 bit-bytes 1 assert-eq ;
: test-bytes-eight       8 bit-bytes 1 assert-eq ;
: test-bytes-nine        9 bit-bytes 2 assert-eq ;
: test-bytes-sixteen     16 bit-bytes 2 assert-eq ;
: test-bytes-large       100 bit-bytes 13 assert-eq ;

: test-byte-zero         0 bit-byte 0 assert-eq ;
: test-byte-seven        7 bit-byte 0 assert-eq ;
: test-byte-eight        8 bit-byte 1 assert-eq ;
: test-byte-fifteen      15 bit-byte 1 assert-eq ;

: test-pos-zero          0 bit-pos 0 assert-eq ;
: test-pos-seven         7 bit-pos 7 assert-eq ;
: test-pos-eight-wraps   8 bit-pos 0 assert-eq ;
: test-pos-fifteen       15 bit-pos 7 assert-eq ;

: test-mask-zero         0 bit-mask 1 assert-eq ;
: test-mask-three        3 bit-mask 8 assert-eq ;
: test-mask-seven        7 bit-mask 128 assert-eq ;

: test-empty-bit-zero    setup-empty  0 tb-flags bit@  0 assert-eq ;
: test-empty-bit-mid     setup-empty  17 tb-flags bit@  0 assert-eq ;

: test-set-then-fetch    setup-empty
    5 tb-flags bit-set
    5 tb-flags bit@  1 assert-eq ;

: test-set-byte-boundary setup-empty
    8 tb-flags bit-set
    8 tb-flags bit@  1 assert-eq ;

: test-set-does-not-leak setup-empty
    5 tb-flags bit-set
    4 tb-flags bit@  0 assert-eq ;

: test-set-does-not-bleed-up setup-empty
    5 tb-flags bit-set
    6 tb-flags bit@  0 assert-eq ;

: test-set-cross-byte    setup-empty
    7 tb-flags bit-set
    8 tb-flags bit@  0 assert-eq ;

: test-set-far-bit       setup-empty
    100 tb-flags bit-set
    100 tb-flags bit@  1 assert-eq ;

: test-reset-from-ones   setup-all-ones
    3 tb-flags bit-reset
    3 tb-flags bit@  0 assert-eq ;

: test-reset-keeps-others setup-all-ones
    3 tb-flags bit-reset
    4 tb-flags bit@  1 assert-eq ;

: test-reset-keeps-byte-low setup-all-ones
    3 tb-flags bit-reset
    0 tb-flags bit@  1 assert-eq ;

: test-flip-zero-to-one  setup-empty
    9 tb-flags bit-flip
    9 tb-flags bit@  1 assert-eq ;

: test-flip-one-to-zero  setup-all-ones
    9 tb-flags bit-flip
    9 tb-flags bit@  0 assert-eq ;

: test-flip-twice-roundtrip setup-empty
    11 tb-flags bit-flip
    11 tb-flags bit-flip
    11 tb-flags bit@  0 assert-eq ;

: test-store-truthy      setup-empty
    1 5 tb-flags bit!
    5 tb-flags bit@  1 assert-eq ;

: test-store-falsy       setup-all-ones
    0 5 tb-flags bit!
    5 tb-flags bit@  0 assert-eq ;

: test-store-non-one-truthy setup-empty
    42 5 tb-flags bit!
    5 tb-flags bit@  1 assert-eq ;

: test-erase-clears-set  setup-all-ones
    32 tb-flags bit-erase
    7 tb-flags bit@  0 assert-eq ;

: test-erase-respects-length  setup-all-ones
    8 tb-flags bit-erase
    15 tb-flags bit@  1 assert-eq ;
