\ stdlib/test-lib.fs — assertions for the Forth test harness.
\
\ The Python side reads _result (0 = pass, non-zero = fail), and on failure
\ reads _expected and _actual to report the mismatch.

variable _result
variable _expected
variable _actual

\ fail the test if actual does not equal expected, recording both for diagnosis
: assert-eq  ( actual expected -- )
    2dup = if
        2drop
    else
        _expected !
        _actual !
        1 _result !
    then ;

\ fail the test if flag is zero
: assert-true  ( flag -- )
    if else 1 _result ! then ;

\ fail the test if flag is non-zero
: assert-false  ( flag -- )
    if 1 _result ! then ;
