include test-lib.fs
require ../app/plasma.fs

: test-wave-at-0     0  wave@   0 assert-eq ;
: test-wave-at-7     7  wave@   7 assert-eq ;
: test-wave-at-8     8  wave@   7 assert-eq ;
: test-wave-at-15    15 wave@   0 assert-eq ;
: test-wave-at-16    16 wave@   0 assert-eq ;
: test-wave-at-23    23 wave@   7 assert-eq ;
: test-wave-at-31    31 wave@   0 assert-eq ;

: test-wave-wraps-mod32
    32 wave@  0 wave@  assert-eq ;

: test-wave-wraps-large
    100 wave@  4 wave@  assert-eq ;
