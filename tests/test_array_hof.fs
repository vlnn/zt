include test-lib.fs
include array-hof.fs

\ -- shared fixtures --

w: ws       10 , 20 , 30 , 40 , ;
w: ws-empty ;
c: cs       1 c, 2 c, 3 c, 4 c, 5 c, ;
b: bs       $05 c, ;                      \ 8 bits: 10100000 LSB-first

variable sink

: bump  ( v -- )       sink +! ;
: dbl   ( v -- v' )    2* ;
: inc   ( v -- v' )    1+ ;
: invert-bit  ( b -- b' )   1 xor ;
: add   ( a v -- a+v ) + ;
: even? ( v -- flag )  1 and 0= ;
: nz?   ( v -- flag )  0= invert ;
: eq30? ( v -- flag )  30 = ;
: eq3?  ( v -- flag )  3 = ;

\ -- for-each: side effect via sink --

: test-for-each-word-sums-elements
    0 sink !
    ws ['] bump for-each-word
    sink @                                         100 assert-eq ;

: test-for-each-byte-sums-elements
    0 sink !
    cs ['] bump for-each-byte
    sink @                                          15 assert-eq ;

: test-for-each-bit-sums-elements
    0 sink !
    bs ['] bump for-each-bit
    sink @                                           2 assert-eq ;

: test-for-each-word-empty-leaves-sink
    99 sink !
    ws-empty ['] bump for-each-word
    sink @                                          99 assert-eq ;

\ -- map: in-place mutation --

w: ws-for-map  1 , 2 , 3 , ;

: test-map-word-doubles
    ws-for-map ['] dbl map-word
    ws-for-map 0 a-word@                            2 assert-eq ;

: test-map-word-doubles-last
    ws-for-map ['] dbl map-word
    ws-for-map ['] dbl map-word
    ws-for-map 2 a-word@                           12 assert-eq ;

c: cs-for-map  10 c, 20 c, 30 c, ;

: test-map-byte-increments
    cs-for-map ['] inc map-byte
    cs-for-map 1 a-byte@                           21 assert-eq ;

b: bs-for-map  $00 c, ;

: test-map-bit-inverts-all
    bs-for-map ['] invert-bit map-bit
    bs-for-map 0 a-bit@                             1 assert-eq ;

: test-map-bit-inverts-last-bit
    bs-for-map ['] invert-bit map-bit
    bs-for-map 7 a-bit@                             1 assert-eq ;

\ -- reduce: fold --

: test-reduce-word-sum
    0 ws ['] add reduce-word                      100 assert-eq ;

: test-reduce-byte-sum
    0 cs ['] add reduce-byte                       15 assert-eq ;

: test-reduce-bit-sum
    0 bs ['] add reduce-bit                         2 assert-eq ;

: test-reduce-word-empty-returns-acc
    42 ws-empty ['] add reduce-word                42 assert-eq ;

: test-reduce-word-uses-initial-acc
    1000 ws ['] add reduce-word                  1100 assert-eq ;

\ -- count-if --

: test-count-if-word-evens
    ws ['] even? count-if-word                      4 assert-eq ;

: test-count-if-byte-nonzero
    cs ['] nz? count-if-byte                        5 assert-eq ;

: test-count-if-bit-nonzero
    bs ['] nz? count-if-bit                         2 assert-eq ;

: test-count-if-empty-returns-zero
    ws-empty ['] even? count-if-word                0 assert-eq ;

\ -- any? --

: test-any-word-finds-30
    ws ['] eq30? any?-word                         -1 assert-eq ;

: ge100?  ( v -- flag )  99 > ;

: test-any-word-no-match
    ws ['] ge100? any?-word                         0 assert-eq ;

: test-any-empty-returns-false
    ws-empty ['] eq30? any?-word                    0 assert-eq ;

\ -- all? --

: positive?  ( v -- flag )  0 > ;
: lt100?     ( v -- flag )  100 < ;

: test-all-word-all-positive
    ws ['] positive? all?-word                     -1 assert-eq ;

: test-all-word-not-all-lt-30
    ws ['] eq30? all?-word                          0 assert-eq ;

: test-all-empty-vacuously-true
    ws-empty ['] eq30? all?-word                   -1 assert-eq ;

\ -- index-of? --

: test-index-of-word-flag-on-found
    ws ['] eq30? index-of?-word                     \ ( i flag )
    nip                                             \ flag only
    -1 assert-eq ;

: test-index-of-word-index-on-found
    ws ['] eq30? index-of?-word                     \ ( i flag )
    drop                                            \ index only
    2 assert-eq ;

: test-index-of-word-flag-on-missing
    ws ['] ge100? index-of?-word
    nip
    0 assert-eq ;

: test-index-of-byte-finds-3
    cs ['] eq3? index-of?-byte
    drop
    2 assert-eq ;

: test-index-of-empty-returns-zero-flag
    ws-empty ['] eq30? index-of?-word
    nip
    0 assert-eq ;
