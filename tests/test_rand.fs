include test-lib.fs
include rand.fs

: test-seed-persists
    42 seed!  rnd-seed @  42 assert-eq ;

: test-rnd-is-deterministic
    7 seed!  rnd
    7 seed!  rnd  assert-eq ;

: test-rnd-changes-across-calls
    1 seed!  rnd rnd <>  assert-true ;

: test-random-one-is-zero
    99 seed!  1 random  0 assert-eq ;

: test-random-bounded
    1 seed!
    0
    32 0 do  10 random max  loop
    10 <  assert-true ;

: test-random-nonneg
    12345 seed!
    0
    32 0 do  100 random min  loop
    0<  assert-false ;

: test-between-lower-bound
    1 seed!
    100
    32 0 do  5 10 between min  loop
    5 <  assert-false ;

: test-between-upper-bound
    1 seed!
    0
    32 0 do  5 10 between max  loop
    10 >  assert-false ;

: test-one-in-one-always-true
    1 seed!  1 one-in  assert-true ;
