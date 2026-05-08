include test-lib.fs
require ../lib/plot.fs

\ Spectrum screen at $4000-$57FF.  Reference addresses:
\   pixel (0,0)   → $4000, mask $80
\   pixel (7,0)   → $4000, mask $01
\   pixel (8,0)   → $4001, mask $80
\   pixel (0,1)   → $4100, mask $80   (y bit 0 → addr bit 8)
\   pixel (0,8)   → $4020, mask $80   (y bits 3-5 → addr bits 5-7)
\   pixel (0,64)  → $4800, mask $80   (y bits 6-7 → addr bits 11-12)

: test-byte-origin           0   0  pixel-byte  $4000 assert-eq ;
: test-byte-x-7              7   0  pixel-byte  $4000 assert-eq ;
: test-byte-x-8              8   0  pixel-byte  $4001 assert-eq ;
: test-byte-y-1              0   1  pixel-byte  $4100 assert-eq ;
: test-byte-y-8              0   8  pixel-byte  $4020 assert-eq ;
: test-byte-y-64             0  64  pixel-byte  $4800 assert-eq ;
: test-byte-far-corner     255 191  pixel-byte  $57FF assert-eq ;

: test-mask-x-0              0  pixel-mask  $80 assert-eq ;
: test-mask-x-1              1  pixel-mask  $40 assert-eq ;
: test-mask-x-7              7  pixel-mask  $01 assert-eq ;
: test-mask-x-8              8  pixel-mask  $80 assert-eq ;
: test-mask-x-100          100  pixel-mask  $08 assert-eq ;

\ end-to-end: plot writes the right bit
: test-plot-origin
    0 0 plot  $4000 c@  $80 assert-eq ;

: test-plot-bit-position
    1 0 plot  $4000 c@  $40 assert-eq ;

: test-plot-or-accumulates
    0 0 plot  1 0 plot  $4000 c@  $C0 assert-eq ;

: test-plot-y-1-different-byte
    0 1 plot  $4100 c@  $80 assert-eq
    0 1 plot  $4000 c@  0   assert-eq ;
