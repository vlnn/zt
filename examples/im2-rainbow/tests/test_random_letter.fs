include test-lib.fs
require ../app/rainbow.fs

: in-letter-or-space?  ( ch -- flag )
    dup 32 = if drop -1 else dup 64 > swap 91 < and then ;

: count-spaces  ( n -- spaces )
    0 swap 0 do
        random-letter 32 = if  1+  then
    loop ;

: test-random-letter-in-range-seed-1
    1 seed!  random-letter in-letter-or-space?  assert-true ;

: test-random-letter-in-range-seed-99
    99 seed!  random-letter in-letter-or-space?  assert-true ;

: test-random-letter-in-range-seed-12345
    12345 seed!  random-letter in-letter-or-space?  assert-true ;

: test-random-letter-changes-across-calls
    1 seed!  random-letter random-letter <>  assert-true ;

: test-random-letter-produces-spaces
    1 seed!  200 count-spaces  0 >  assert-true ;
