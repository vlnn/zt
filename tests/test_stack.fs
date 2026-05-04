include test-lib.fs
require core.fs

: test-dup        7 dup +        14 assert-eq ;
: test-drop       1 2 drop        1 assert-eq ;
: test-swap       5 3 swap        5 assert-eq ;
: test-over       5 3 over        5 assert-eq ;
: test-nip        1 2 nip         2 assert-eq ;
: test-2dup       1 2 2dup + +    5 assert-eq ;
: test-2drop      1 2 3 2drop     1 assert-eq ;

: test-?dup-nonzero-leaves-two-copies
    7 ?dup +                        14 assert-eq ;

: test-?dup-zero-leaves-just-zero
    99 0 ?dup +                     99 assert-eq ;

: test-?dup-negative-leaves-two-copies
    -3 ?dup +                       -6 assert-eq ;

: test-?dup-preserves-stack-below
    42 7 ?dup drop drop             42 assert-eq ;
