include test-lib.fs
include udg.fs

create tu-glyph
    $01 c, $02 c, $04 c, $08 c,
    $10 c, $20 c, $40 c, $80 c,

: test-udg-addr-slot-0
    0 udg-addr $FF58 assert-eq ;

: test-udg-addr-slot-1
    1 udg-addr $FF60 assert-eq ;

: test-udg-addr-slot-20
    20 udg-addr $FFF8 assert-eq ;

: test-udg-char-slot-0
    0 udg-char 144 assert-eq ;

: test-udg-char-slot-20
    20 udg-char 164 assert-eq ;

: test-udg-store-first-byte
    tu-glyph 0 udg!
    $FF58 c@ $01 assert-eq ;

: test-udg-store-last-byte
    tu-glyph 0 udg!
    $FF58 7 + c@ $80 assert-eq ;

: test-udg-store-slot-1-starts-at-ff60
    tu-glyph 1 udg!
    $FF60 c@ $01 assert-eq ;

: test-udg-store-slot-1-last-byte
    tu-glyph 1 udg!
    $FF67 c@ $80 assert-eq ;

: test-screen-base-origin
    0 0 screen-base $4000 assert-eq ;

: test-screen-base-col5-row0
    5 0 screen-base $4005 assert-eq ;

: test-screen-base-col0-row1
    0 1 screen-base $4020 assert-eq ;

: test-screen-base-col0-row8
    0 8 screen-base $4800 assert-eq ;

: test-screen-base-col0-row16
    0 16 screen-base $5000 assert-eq ;

: test-screen-base-col31-row23
    31 23 screen-base $50FF assert-eq ;

: test-draw-udg-first-line
    tu-glyph 0 udg!
    0 0 0 draw-udg
    $4000 c@ $01 assert-eq ;

: test-draw-udg-last-line
    tu-glyph 0 udg!
    0 0 0 draw-udg
    $4700 c@ $80 assert-eq ;

: test-draw-udg-offset-cell
    tu-glyph 0 udg!
    0 10 5 draw-udg
    $40AA c@ $01 assert-eq ;

: test-erase-cell-first-line
    tu-glyph 0 udg!
    0 0 0 draw-udg
    0 0 erase-cell
    $4000 c@ 0 assert-eq ;

: test-erase-cell-last-line
    tu-glyph 0 udg!
    0 0 0 draw-udg
    0 0 erase-cell
    $4700 c@ 0 assert-eq ;
