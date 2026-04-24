include test-lib.fs
require ../lib/rng.fs

: test-seed-persists
    42 seed!  rnd-seed @  42 assert-eq ;

: test-rnd-advances-seed
    1 seed!  rnd  rnd-seed @  assert-eq ;

: test-rnd-is-deterministic
    1 seed!  rnd
    1 seed!  rnd
    assert-eq ;

: test-rnd-changes-across-calls
    1 seed!  rnd rnd <>  assert-true ;

: test-random-one-always-zero
    99 seed!  1 random  0 assert-eq ;

: test-random-bounded-by-n
    1 seed!
    0
    16 0 do  10 random max  loop
    10 <  assert-true ;

: test-random-nonnegative
    12345 seed!
    0
    32 0 do  10 random min  loop
    0<  assert-false ;
