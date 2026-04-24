include test-lib.fs
require core.fs
require ../lib/timing.fs
require ../app/reaction.fs

: test-ms-per-frame-is-20   ms-per-frame  20 assert-eq ;

: test-frames-to-ms-zero    0 frames>ms   0 assert-eq ;
: test-frames-to-ms-one     1 frames>ms  20 assert-eq ;
: test-frames-to-ms-fifty  50 frames>ms  1000 assert-eq ;

: test-digit-to-char-zero   0 digit>char  48 assert-eq ;
: test-digit-to-char-nine   9 digit>char  57 assert-eq ;

: test-pick-digit-below-ten
    1 seed!
    0
    32 0 do  pick-digit max  loop
    10 <  assert-true ;

: test-pick-digit-nonnegative
    7 seed!
    0
    32 0 do  pick-digit min  loop
    0<  assert-false ;

: test-random-delay-at-least-min
    1 seed!
    32767
    16 0 do  random-delay min  loop
    min-delay <  assert-false ;

: test-random-delay-below-max
    1 seed!
    0
    16 0 do  random-delay max  loop
    max-delay <  assert-true ;

: test-check-key-zero-zero      0 48 check-key  assert-true ;
: test-check-key-nine-nine      9 57 check-key  assert-true ;
: test-check-key-zero-one       0 49 check-key  assert-false ;
: test-check-key-digit-letter   5 65 check-key  assert-false ;

: test-reset-stats-clears-total
    reset-stats  total-ms @       0 assert-eq ;
: test-reset-stats-clears-count
    reset-stats  round-count @    0 assert-eq ;

: test-record-round-accumulates
    reset-stats
    100 record-round
    200 record-round
    total-ms @  300 assert-eq ;

: test-record-round-increments-count
    reset-stats
    100 record-round
    200 record-round
    300 record-round
    round-count @  3 assert-eq ;

: test-avg-ms-single-round
    reset-stats  500 record-round
    avg-ms       500 assert-eq ;

: test-avg-ms-three-rounds
    reset-stats
    100 record-round
    200 record-round
    300 record-round
    avg-ms       200 assert-eq ;
