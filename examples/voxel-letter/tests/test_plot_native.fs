include test-lib.fs
require ../lib/plot_native.fs

\ Same end-to-end checks as test_plot.fs, but only those that don't
\ depend on pixel-byte / pixel-mask (which the native version
\ inlines).

: clear-screen     $4000 6144 0 fill ;

: test-plot-origin
    clear-screen
    0 0 plot  $4000 c@  $80 assert-eq ;

: test-plot-bit-1
    clear-screen
    1 0 plot  $4000 c@  $40 assert-eq ;

: test-plot-bit-7
    clear-screen
    7 0 plot  $4000 c@  $01 assert-eq ;

: test-plot-x-8-second-byte
    clear-screen
    8 0 plot  $4001 c@  $80 assert-eq ;

: test-plot-y-1-different-row
    clear-screen
    0 1 plot  $4100 c@  $80 assert-eq
              $4000 c@  0 assert-eq ;

: test-plot-y-8-band-shift
    clear-screen
    0 8 plot  $4020 c@  $80 assert-eq ;

: test-plot-y-64-second-band
    clear-screen
    0 64 plot  $4800 c@  $80 assert-eq ;

: test-plot-far-corner
    clear-screen
    255 191 plot  $57FF c@  $01 assert-eq ;

: test-plot-or-accumulates
    clear-screen
    0 0 plot  1 0 plot
    $4000 c@  $C0 assert-eq ;
