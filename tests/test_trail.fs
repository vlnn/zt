include test-lib.fs
include trail.fs

create tt-buf  16 allot

: setup-8  tt-buf 8 trail-init ;

: test-init-len-is-zero
    setup-8  trail-len@ 0 assert-eq ;

: test-push-once-len-is-one
    setup-8  42 trail-push  trail-len@ 1 assert-eq ;

: test-push-three-len-is-three
    setup-8
    10 trail-push  20 trail-push  30 trail-push
    trail-len@ 3 assert-eq ;

: test-oldest-is-first-pushed
    setup-8
    10 trail-push  20 trail-push  30 trail-push
    0 trail@ 10 assert-eq ;

: test-newest-is-last-pushed
    setup-8
    10 trail-push  20 trail-push  30 trail-push
    2 trail@ 30 assert-eq ;

: test-middle-item
    setup-8
    10 trail-push  20 trail-push  30 trail-push
    1 trail@ 20 assert-eq ;

: test-wrap-len-caps-at-capacity
    setup-8
    10 0 do i trail-push loop
    trail-len@ 8 assert-eq ;

: test-wrap-oldest-is-dropped
    setup-8
    10 0 do i trail-push loop
    0 trail@ 2 assert-eq ;

: test-wrap-newest-preserved
    setup-8
    10 0 do i trail-push loop
    7 trail@ 9 assert-eq ;

: test-reset-clears-len
    setup-8
    42 trail-push  trail-reset
    trail-len@ 0 assert-eq ;

: test-pack-unpack-roundtrip-col
    5 3 pack-xy unpack-xy  drop  5 assert-eq ;

: test-pack-unpack-roundtrip-row
    5 3 pack-xy unpack-xy  nip   3 assert-eq ;

: test-pack-boundary-zero
    0 0 pack-xy 0 assert-eq ;

: test-pack-boundary-max
    31 23 pack-xy unpack-xy drop 31 assert-eq ;
