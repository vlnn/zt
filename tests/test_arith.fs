include test-lib.fs

: test-plus       3 4 +           7 assert-eq ;
: test-minus      10 3 -          7 assert-eq ;
: test-star       6 7 *          42 assert-eq ;
: test-negate     5 negate       -5 assert-eq ;
: test-abs-pos    7 abs           7 assert-eq ;
: test-abs-neg   -7 abs           7 assert-eq ;
: test-one-plus   41 1+          42 assert-eq ;
: test-one-minus  43 1-          42 assert-eq ;
