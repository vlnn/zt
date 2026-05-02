include test-lib.fs
include core.fs
include sprites.fs
include udg.fs

\ -- blank8: 8-byte all-zero char-aligned source ----------------------------

: test-blank8-first-byte-zero
    blank8 c@                      0 assert-eq ;

: test-blank8-last-byte-zero
    blank8 7 + c@                  0 assert-eq ;

: test-blank8-spans-eight-bytes
    blank8 8 +  blank8 -           8 assert-eq ;

\ -- blank-shifted: 128-byte all-zero pixel-aligned source ------------------

: test-blank-shifted-first-byte-zero
    blank-shifted c@               0 assert-eq ;

: test-blank-shifted-mid-byte-zero
    blank-shifted 64 + c@          0 assert-eq ;

: test-blank-shifted-last-byte-zero
    blank-shifted 127 + c@         0 assert-eq ;

\ -- erase8: clears the eight scanlines of a char cell ----------------------

: test-erase8-clears-first-line
    $FF  5 3 screen-base c!
    lock-sprites
    5 3 erase8
    5 3 screen-base c@             0 assert-eq ;

: test-erase8-clears-last-line
    $FF  5 3 screen-base 7 cell-line-addr c!
    lock-sprites
    5 3 erase8
    5 3 screen-base 7 cell-line-addr c@   0 assert-eq ;

: test-erase8-leaves-left-neighbor-untouched
    $AA  4 3 screen-base c!
    lock-sprites
    5 3 erase8
    4 3 screen-base c@             $AA assert-eq ;

: test-erase8-leaves-right-neighbor-untouched
    $AA  6 3 screen-base c!
    lock-sprites
    5 3 erase8
    6 3 screen-base c@             $AA assert-eq ;

: test-erase8-consumes-two-stack-items
    99  5 3
    lock-sprites erase8
    99 assert-eq ;

\ -- erase8x: pixel-aligned erase -------------------------------------------

: test-erase8x-aligned-clears-cell-first-line
    $FF  5 3 screen-base c!
    lock-sprites
    40 24 erase8x
    5 3 screen-base c@             0 assert-eq ;

: test-erase8x-aligned-clears-cell-last-line
    $FF  5 3 screen-base 7 cell-line-addr c!
    lock-sprites
    40 24 erase8x
    5 3 screen-base 7 cell-line-addr c@   0 assert-eq ;

: test-erase8x-consumes-two-stack-items
    99  40 24
    lock-sprites erase8x
    99 assert-eq ;
