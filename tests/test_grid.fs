include test-lib.fs
include grid.fs

create tb-board  25 allot

: setup-5x5  tb-board 5 5 grid-set!  0 grid-clear ;

: test-dimensions-roundtrip
    setup-5x5  grid-w @ 5 assert-eq ;

: test-height-roundtrip
    setup-5x5  grid-h @ 5 assert-eq ;

: test-area
    setup-5x5  grid-area 25 assert-eq ;

: test-store-fetch-roundtrip
    setup-5x5
    42 2 3 grid!
    2 3 grid@  42 assert-eq ;

: test-clear-writes-all-cells
    setup-5x5
    99 grid-clear
    0 0 grid@ 99 assert-eq ;

: test-clear-writes-last-cell
    setup-5x5
    99 grid-clear
    4 4 grid@ 99 assert-eq ;

: test-fill-row
    setup-5x5
    7 2 fill-row
    0 2 grid@ 7 assert-eq ;

: test-fill-row-does-not-leak
    setup-5x5
    7 2 fill-row
    0 1 grid@ 0 assert-eq ;

: test-fill-col
    setup-5x5
    3 1 fill-col
    1 0 grid@ 3 assert-eq ;

: test-fill-col-full-height
    setup-5x5
    3 1 fill-col
    1 4 grid@ 3 assert-eq ;

: test-in-bounds-inside
    setup-5x5
    2 2 in-bounds? assert-true ;

: test-in-bounds-origin
    setup-5x5
    0 0 in-bounds? assert-true ;

: test-in-bounds-last
    setup-5x5
    4 4 in-bounds? assert-true ;

: test-in-bounds-neg-col
    setup-5x5
    -1 0 in-bounds? assert-false ;

: test-in-bounds-neg-row
    setup-5x5
    0 -1 in-bounds? assert-false ;

: test-in-bounds-too-far-col
    setup-5x5
    5 0 in-bounds? assert-false ;

: test-in-bounds-too-far-row
    setup-5x5
    0 5 in-bounds? assert-false ;

: test-neighbours4-isolated
    setup-5x5
    2 2 neighbours4 0 assert-eq ;

: test-neighbours4-one-north
    setup-5x5
    1 2 1 grid!
    2 2 neighbours4 1 assert-eq ;

: test-neighbours4-all-four
    setup-5x5
    1 2 1 grid!   1 2 3 grid!
    1 1 2 grid!   1 3 2 grid!
    2 2 neighbours4 4 assert-eq ;

: test-neighbours4-ignores-diagonal
    setup-5x5
    1 1 1 grid!  1 3 1 grid!  1 1 3 grid!  1 3 3 grid!
    2 2 neighbours4 0 assert-eq ;

: test-neighbours8-all-eight
    setup-5x5
    1 1 1 grid!  1 2 1 grid!  1 3 1 grid!
    1 1 2 grid!                1 3 2 grid!
    1 1 3 grid!  1 2 3 grid!  1 3 3 grid!
    2 2 neighbours8 8 assert-eq ;

: test-neighbours-count-counts-nonzero-any-value
    setup-5x5
    99 2 1 grid!
    2 2 neighbours4 1 assert-eq ;
