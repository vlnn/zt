include test-lib.fs
include array.fs

w: ws  100  200  300  400 ;
c: cs  $A0  $B1  $C2  $D3  $E4 ;
b: bs
    1 0 1 0 1 0 1 0     \ first byte: $55
    0 1 0 1 0 1 0 1     \ second byte: $AA
    1 1 1 1 0 0 0 0 ;   \ third byte: $0F

: test-warray-count       ws a-count                 4 assert-eq ;
: test-warray-read-0      ws 0 a-word@             100 assert-eq ;
: test-warray-read-1      ws 1 a-word@             200 assert-eq ;
: test-warray-read-3      ws 3 a-word@             400 assert-eq ;

: test-warray-write-roundtrip
    777 ws 2 a-word!
    ws 2 a-word@                                   777 assert-eq ;

: test-carray-count       cs a-count                 5 assert-eq ;
: test-carray-read-0      cs 0 a-byte@             $A0 assert-eq ;
: test-carray-read-4      cs 4 a-byte@             $E4 assert-eq ;

: test-carray-write-roundtrip
    $7F cs 2 a-byte!
    cs 2 a-byte@                                   $7F assert-eq ;

: test-barray-count       bs a-count                24 assert-eq ;

\ $55 = 01010101: bits 0,2,4,6 are 1; 1,3,5,7 are 0
: test-barray-bit-0       bs 0 a-bit@                1 assert-eq ;
: test-barray-bit-1       bs 1 a-bit@                0 assert-eq ;
: test-barray-bit-2       bs 2 a-bit@                1 assert-eq ;
: test-barray-bit-7       bs 7 a-bit@                0 assert-eq ;
\ $AA = 10101010 in next byte (bits 8..15): 0,2,4,6 are 0; 1,3,5,7 are 1
: test-barray-bit-8       bs 8 a-bit@                0 assert-eq ;
: test-barray-bit-9       bs 9 a-bit@                1 assert-eq ;
: test-barray-bit-15      bs 15 a-bit@               1 assert-eq ;
\ $0F = 00001111 in third byte (bits 16..23): 0,1,2,3 are 1; 4,5,6,7 are 0
: test-barray-bit-16      bs 16 a-bit@               1 assert-eq ;
: test-barray-bit-19      bs 19 a-bit@               1 assert-eq ;
: test-barray-bit-20      bs 20 a-bit@               0 assert-eq ;
: test-barray-bit-23      bs 23 a-bit@               0 assert-eq ;

: test-barray-set-clear-bit
    1 bs 1 a-bit!
    bs 1 a-bit@                                      1 assert-eq ;

: test-barray-clear-set-bit
    0 bs 0 a-bit!
    bs 0 a-bit@                                      0 assert-eq ;

: test-barray-set-bit-doesnt-touch-neighbor
    0 bs 0 a-bit!
    1 bs 1 a-bit!
    bs 2 a-bit@                                      1 assert-eq ;
