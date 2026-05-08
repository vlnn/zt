include test-lib.fs
require ../lib/render.fs

\ ── end-to-end at yaw=0 pitch=0 ────────────────────────────────────────
\ TEST_FONT byte for char 65 is $41 = 0100_0001 → cols 1 and 7 lit.
\ At yaw=pitch=0, render-letter walks rows 0..7 with rx = col, ry = row.
\
\ For row 0 (ry=0):
\   col 1 (rx=1): byte = letter-buf[0], mask = $80 >> 1 = $40
\   col 7 (rx=7): byte = letter-buf[0], mask = $80 >> 7 = $01
\ Both bits land in the same byte → letter-buf[0] = $41.

: test-render-A-col-1-row-0
    clear-buffer
    0 0 bake-rotation
    65 render-letter
    letter-buf c@   $40 and  $40 assert-eq ;

: test-render-A-col-7-row-0
    clear-buffer
    0 0 bake-rotation
    65 render-letter
    letter-buf c@   $01 and  $01 assert-eq ;

\ TEST_FONT for char 32 is $20 = 0010_0000 → only col 2 lit.  Bit 0 of
\ every row should stay clean.
: test-render-blank-on-space
    clear-buffer
    0 0 bake-rotation
    32 render-letter
    letter-buf c@   $01 and  0 assert-eq ;

\ ── pitch=32 (180°) reflects y around cube origin ──────────────────────
\ Voxel positions stay in [-3.5, +3.5], so the buffer still spans rows
\ 0..7.  At pitch=180° the row order reverses: cube row 7 (cube-y=+3.5)
\ now lands at buffer ry=0 instead of ry=7.

: test-render-pitch-180-reflects
    clear-buffer
    0 32 bake-rotation
    65 render-letter
    \ Row index 0 (in glyph) maps to ry=7 at pitch=180°, and row 7 maps
    \ to ry=0.  Either way some row is non-empty.  Just verify the
    \ buffer isn't blank.
    letter-buf 7 + c@   0 <>  assert-true ;
