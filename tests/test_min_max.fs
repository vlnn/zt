include test-lib.fs
require core.fs


\ ---------------------------------------------------------------------------
\ positive operands — the easy cases
\ ---------------------------------------------------------------------------

: test-min-two-positives      5 3 min    3 assert-eq ;
: test-min-swapped            3 5 min    3 assert-eq ;
: test-min-equal-positives    7 7 min    7 assert-eq ;
: test-max-two-positives      5 3 max    5 assert-eq ;
: test-max-swapped            3 5 max    5 assert-eq ;
: test-max-equal-positives    7 7 max    7 assert-eq ;


\ ---------------------------------------------------------------------------
\ zero boundary
\ ---------------------------------------------------------------------------

: test-min-zero-and-positive     0  5 min   0 assert-eq ;
: test-min-positive-and-zero     5  0 min   0 assert-eq ;
: test-max-zero-and-positive     0  5 max   5 assert-eq ;
: test-max-positive-and-zero     5  0 max   5 assert-eq ;


\ ---------------------------------------------------------------------------
\ negative operands — where the unsigned primitive used to misbehave
\ ---------------------------------------------------------------------------

: test-min-two-negatives      -3 -5 min  -5 assert-eq ;
: test-min-negatives-swapped  -5 -3 min  -5 assert-eq ;
: test-max-two-negatives      -3 -5 max  -3 assert-eq ;
: test-max-negatives-swapped  -5 -3 max  -3 assert-eq ;


\ ---------------------------------------------------------------------------
\ mixed signs — the key failure mode: treating -N as a huge unsigned
\ ---------------------------------------------------------------------------

: test-min-neg-and-pos        -5  5 min  -5 assert-eq ;
: test-min-pos-and-neg         5 -5 min  -5 assert-eq ;
: test-max-neg-and-pos        -5  5 max   5 assert-eq ;
: test-max-pos-and-neg         5 -5 max   5 assert-eq ;

: test-min-neg-and-zero       -1  0 min  -1 assert-eq ;
: test-min-zero-and-neg        0 -1 min  -1 assert-eq ;
: test-max-neg-and-zero       -1  0 max   0 assert-eq ;
: test-max-zero-and-neg        0 -1 max   0 assert-eq ;


\ ---------------------------------------------------------------------------
\ the shape min/max get used in for clamping — 0 and board-width-1 style
\ ---------------------------------------------------------------------------

: test-clamp-negative-to-zero   -5  0 max  31 min    0 assert-eq ;
: test-clamp-zero-stays-zero     0  0 max  31 min    0 assert-eq ;
: test-clamp-in-range-stays     15  0 max  31 min   15 assert-eq ;
: test-clamp-above-max          99  0 max  31 min   31 assert-eq ;
