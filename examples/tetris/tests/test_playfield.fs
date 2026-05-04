\ Unit tests for playfield mechanics.  Exercises pf-row-full?,
\ pf-compact, and the preset-counting path in isolation, without
\ booting the full game loop.

require test-lib.fs
require ../lib/sprites.fs
require ../lib/pieces.fs
require ../lib/playfield.fs

variable _fr-attr
variable _fr-row
variable _fr-gap

: setup-pf       ( -- )    pf-bind  pf-clear ;

: fill-row       ( attr row -- )
    _fr-row ! _fr-attr !
    pf-cols 0 do
        _fr-attr @  i  _fr-row @  pf!
    loop ;

: fill-row-preset ( attr row -- )
    _fr-row ! _fr-attr !
    pf-cols 0 do
        _fr-attr @ $80 or  i  _fr-row @  pf!
    loop ;

: write-row-skip-col ( attr gap-col row -- )
    _fr-row ! _fr-gap ! _fr-attr !
    pf-cols 0 do
        i _fr-gap @ <> if
            _fr-attr @  i  _fr-row @  pf!
        then
    loop ;

: stamp-cell-at  ( v col row -- )    pf! ;


\ pf-row-full?

: test-full-row  ( -- )
    setup-pf
    $42 17 fill-row
    17 pf-row-full? assert-true ;

: test-partial-row  ( -- )
    setup-pf
    $42 5 17 write-row-skip-col
    17 pf-row-full? assert-false ;

: test-empty-row-not-full  ( -- )
    setup-pf
    17 pf-row-full? assert-false ;


\ pf-compact: full row at bottom should be reported and removed

: test-compact-clears-one-row  ( -- )
    setup-pf
    $42 17 fill-row
    pf-compact
    pf-cleared-count @ 1 assert-eq ;

: test-compact-counts-presets  ( -- )
    setup-pf
    $42 17 fill-row-preset
    pf-compact
    pf-presets-cleared @ 10 assert-eq ;

: test-compact-leaves-empty-cleared-row  ( -- )
    setup-pf
    $42 17 fill-row
    pf-compact
    0 17 pf@ 0 assert-eq ;

: test-compact-shifts-row-down  ( -- )
    setup-pf
    $42 5 16 stamp-cell-at
    $43 17 fill-row
    pf-compact
    5 17 pf@ $42 assert-eq ;

: test-compact-no-rows-clear-when-empty  ( -- )
    setup-pf
    pf-compact
    pf-cleared-count @ 0 assert-eq ;

: test-compact-leaves-non-full-rows-alone  ( -- )
    setup-pf
    $42 5 16 write-row-skip-col
    pf-compact
    pf-cleared-count @ 0 assert-eq ;


\ Multi-row clears

: test-compact-clears-two-rows  ( -- )
    setup-pf
    $42 16 fill-row
    $43 17 fill-row
    pf-compact
    pf-cleared-count @ 2 assert-eq ;


\ Regression: piece-paint must render the active piece at screen cells
\ derived from (pf-col + 11, pf-row + 2).  An earlier transpose bug
\ swapped the two and made the I-piece appear as a vertical bar on
\ the left side of the playfield, drifting sideways under gravity.
\ The I-piece at spawn (col=3, row=0, rot=0) has filled cells at
\ pf row 1, cols 3..6 → screen row 3, cols 14..17.

require ../lib/piece.fs

\ ZX Spectrum attribute screen base.

$5800 constant attr-base

: attr@ ( scol srow -- attr )    32 *  +  attr-base +  c@ ;

: place-i-piece-at-spawn ( -- )
    piece-i 0 3 0 piece-try-place drop ;

: test-i-piece-row-cells-painted-horizontally ( -- )
    setup-pf
    place-i-piece-at-spawn
    piece-paint
    14 3 attr@  attr-i assert-eq ;

: test-i-piece-row-spans-four-screen-columns ( -- )
    setup-pf
    place-i-piece-at-spawn
    piece-paint
    17 3 attr@  attr-i assert-eq ;

: test-i-piece-does-not-paint-as-vertical-column ( -- )
    setup-pf
    place-i-piece-at-spawn
    piece-paint
    \ The transpose bug would put cells at screen col=12, rows 5..8.
    \ Sample row 7: it should be background, not the piece colour.
    12 7 attr@  attr-i =  assert-false ;


\ Regression: when a piece can't move down further it locks; piece-stamp
\ records the cells in the grid, but the screen painter must repaint
\ those same cells before the next piece spawns — otherwise piece-erase
\ from the previous frame leaves them invisible until a line clear
\ triggers pf-draw-all.

require ../lib/game.fs

: test-locking-piece-stays-on-screen ( -- )
    setup-pf
    \ Drop an O piece against the floor: spawn it, force gravity to fail,
    \ run handle-locked, and check the cells are still painted.
    piece-o 0 4 16 piece-try-place drop
    piece-paint
    \ Now simulate the frame where the piece is about to lock: erase,
    \ then mark locked (gravity would have failed), then handle-locked.
    piece-erase
    -1 piece-locked !
    handle-locked
    \ The O piece occupied PF cells (5, 16) and (6, 16) and (5, 17)
    \ and (6, 17) — bounding box rows 0..1, cols 1..2 with col=4 row=16.
    \ Screen cells: (5+11=16, 16+2=18), (6+11=17, 16+2=18),
    \                (5+11=16, 17+2=19), (6+11=17, 17+2=19).
    16 18 attr@  attr-o assert-eq ;
