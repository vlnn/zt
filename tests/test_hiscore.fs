include test-lib.fs
include hiscore.fs

: test-reset-zeros-score
    hi-reset  hi-score @  0 assert-eq ;

: test-reset-initials-first
    hi-reset  hi-name c@  65 assert-eq ;

: test-reset-initials-last
    hi-reset  hi-name 2 + c@  65 assert-eq ;

: test-set-score
    hi-reset  4242 hi-set-score  hi-score @  4242 assert-eq ;

: test-beats-true
    hi-reset  100 hi-set-score  200 hi-beats?  assert-true ;

: test-beats-false
    hi-reset  500 hi-set-score  100 hi-beats?  assert-false ;

: test-beats-equal-is-false
    hi-reset  500 hi-set-score  500 hi-beats?  assert-false ;

: test-set-name-first
    hi-reset  73 65 78 hi-set-name  hi-name c@  73 assert-eq ;

: test-set-name-second
    hi-reset  73 65 78 hi-set-name  hi-name 1+ c@  65 assert-eq ;

: test-set-name-third
    hi-reset  73 65 78 hi-set-name  hi-name 2 + c@  78 assert-eq ;
