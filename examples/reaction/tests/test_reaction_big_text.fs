include test-lib.fs
require ../lib/big-text.fs

\ TEST_FONT in the simulator stores 8 copies of `c` as the glyph for
\ ASCII char c, so each glyph row is one byte equal to `c`.  We pick
\ glyphs whose bit pattern is easy to predict.
\
\   65 = 'A'  = $41 = 0b01000001 → set columns 1, 7
\   48 = '0'  = $30 = 0b00110000 → set columns 2, 3
\   85 = 'U'  = $55 = 0b01010101 → set columns 1, 3, 5, 7
\   42 = '*'  = $2A = 0b00101010 → set columns 2, 4, 6


: clear-attrs   0 fill-attrs ;
: prep-render   clear-attrs   42 99 big-colours ;


: test-glyph-addr-zero
    32 glyph-addr   $3D00 assert-eq ;

: test-glyph-addr-A
    65 glyph-addr   $3D00 33 8 * +  assert-eq ;

: test-glyph-line-fetches-rom-byte
    \ TEST_FONT replicates the char code 8 times per glyph.
    65 0 glyph-line@   65 assert-eq ;

: test-glyph-line-any-row-same-byte
    65 5 glyph-line@   65 assert-eq ;


: test-bit-on-leftmost-clear
    65 0 bit-on?   assert-false ;

: test-bit-on-second-set
    65 1 bit-on?   assert-true ;

: test-bit-on-rightmost-set
    65 7 bit-on?   assert-true ;

: test-bit-on-zero-byte-anywhere-clear
    0  3 bit-on?   assert-false ;

: test-bit-on-all-byte-anywhere-set
    255 4 bit-on?  assert-true ;


: test-big-emit-paints-on-pixel
    prep-render
    65 0 0 big-emit
    1 0 attr@   42 assert-eq ;

: test-big-emit-paints-off-pixel
    prep-render
    65 0 0 big-emit
    0 0 attr@   99 assert-eq ;

: test-big-emit-paints-rightmost-on
    prep-render
    65 0 0 big-emit
    7 0 attr@   42 assert-eq ;

: test-big-emit-fills-bottom-row
    prep-render
    65 0 0 big-emit
    1 7 attr@   42 assert-eq ;

: test-big-emit-row-7-off-stays-off
    prep-render
    65 0 0 big-emit
    0 7 attr@   99 assert-eq ;

: test-big-emit-honours-col-offset
    prep-render
    65 5 0 big-emit
    6 0 attr@   42 assert-eq ;

: test-big-emit-honours-row-offset
    prep-render
    65 0 10 big-emit
    1 10 attr@  42 assert-eq ;

: test-big-emit-honours-row-offset-bottom
    prep-render
    65 0 10 big-emit
    7 17 attr@  42 assert-eq ;

: test-big-emit-does-not-paint-outside
    prep-render
    65 0 0 big-emit
    8 0 attr@   0 assert-eq ;

: test-big-emit-does-not-paint-below
    prep-render
    65 0 0 big-emit
    1 8 attr@   0 assert-eq ;

: test-big-emit-zero-byte-glyph-all-off
    \ char 32 (' ') has glyph bytes 32 = 0b00100000 → only column 2 set
    prep-render
    32 0 0 big-emit
    0 0 attr@   99 assert-eq ;

: test-big-emit-zero-byte-glyph-col-2-on
    prep-render
    32 0 0 big-emit
    2 0 attr@   42 assert-eq ;

: test-big-emit-digit-zero-col-2-on
    \ '0' = 48 = 0b00110000 → columns 2, 3 set
    prep-render
    48 0 0 big-emit
    2 0 attr@   42 assert-eq ;

: test-big-emit-digit-zero-col-3-on
    prep-render
    48 0 0 big-emit
    3 0 attr@   42 assert-eq ;

: test-big-emit-digit-zero-col-1-off
    prep-render
    48 0 0 big-emit
    1 0 attr@   99 assert-eq ;


: test-big-type-first-char-at-base
    prep-render
    s" AB" 0 0 big-type
    1 0 attr@   42 assert-eq ;

: test-big-type-second-char-eight-cells-right
    prep-render
    s" AB" 0 0 big-type
    \ 'B' = 66 = 0b01000010 → columns 1, 6 set; 'B' at base col 8 → col 9 lit
    9 0 attr@   42 assert-eq ;

: test-big-type-second-char-col-6-shifted
    prep-render
    s" AB" 0 0 big-type
    \ 'B' col 6 → 8 + 6 = 14
    14 0 attr@  42 assert-eq ;

: test-big-type-respects-row-offset
    prep-render
    s" AB" 0 8 big-type
    9 8 attr@   42 assert-eq ;

: test-big-type-leaves-untouched-untouched
    prep-render
    s" A" 0 0 big-type
    \ second slot (cols 8..15) should be all off (untouched zero)
    9 0 attr@   0 assert-eq ;
