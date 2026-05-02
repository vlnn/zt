include test-lib.fs
include logic.fs

: test-le-equal           5 5 <=  assert-true ;
: test-le-less            3 5 <=  assert-true ;
: test-le-greater         7 5 <=  assert-false ;
: test-le-negative-true   -10 -3 <=  assert-true ;
: test-le-negative-false  -3 -10 <=  assert-false ;

: test-ge-equal           5 5 >=  assert-true ;
: test-ge-greater         7 5 >=  assert-true ;
: test-ge-less            3 5 >=  assert-false ;
: test-ge-negative-true   -3 -10 >=  assert-true ;
: test-ge-negative-false  -10 -3 >=  assert-false ;

: test-ule-equal          100 100 u<=  assert-true ;
: test-ule-less           50 100 u<=  assert-true ;
: test-ule-large          50000 60000 u<=  assert-true ;
: test-ule-large-greater  60000 50000 u<=  assert-false ;

: test-between-inside     5 0 10 between?  assert-true ;
: test-between-low-edge   0 0 10 between?  assert-true ;
: test-between-high-edge  10 0 10 between?  assert-true ;
: test-between-below      -1 0 10 between?  assert-false ;
: test-between-above      11 0 10 between?  assert-false ;
: test-between-negative   -5 -10 -1 between?  assert-true ;

: test-clamp-inside       5 0 10 clamp  5 assert-eq ;
: test-clamp-low          -3 0 10 clamp  0 assert-eq ;
: test-clamp-high         99 0 10 clamp  10 assert-eq ;
: test-clamp-low-edge     0 0 10 clamp  0 assert-eq ;
: test-clamp-high-edge    10 0 10 clamp  10 assert-eq ;
: test-clamp-negative     -50 -10 -1 clamp  -10 assert-eq ;
