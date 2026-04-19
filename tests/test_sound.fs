include test-lib.fs
include sound.fs

: test-beep-does-not-crash
    1 50 beep
    42 42 assert-eq ;

: test-beep-consumes-two
    99 1 50 beep
    99 assert-eq ;

: test-click-does-not-crash
    click
    42 42 assert-eq ;

: test-click-no-stack-effect
    99 click  99 assert-eq ;

: test-chirp-no-stack-effect
    99 chirp  99 assert-eq ;

: test-low-beep-no-stack-effect
    99 low-beep  99 assert-eq ;

: test-high-beep-no-stack-effect
    99 high-beep  99 assert-eq ;

: test-tone-consumes-period
    99 100 tone  99 assert-eq ;

: test-multiple-beeps
    1 50 beep  2 60 beep  3 70 beep
    42 42 assert-eq ;
