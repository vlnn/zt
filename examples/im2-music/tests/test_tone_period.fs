include test-lib.fs
require ../app/music.fs

: test-tone-period-c4   0 tone-period  424 assert-eq ;
: test-tone-period-d4   1 tone-period  377 assert-eq ;
: test-tone-period-e4   2 tone-period  336 assert-eq ;
: test-tone-period-f4   3 tone-period  317 assert-eq ;
: test-tone-period-g4   4 tone-period  283 assert-eq ;
: test-tone-period-a4   5 tone-period  252 assert-eq ;
: test-tone-period-b4   6 tone-period  224 assert-eq ;
: test-tone-period-c5   7 tone-period  212 assert-eq ;

: test-tone-period-wraps-at-8
    8 tone-period  0 tone-period  assert-eq ;

: test-tone-period-wraps-at-15
    15 tone-period  7 tone-period  assert-eq ;
