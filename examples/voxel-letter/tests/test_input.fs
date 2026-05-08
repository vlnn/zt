include test-lib.fs
require ../lib/input_voxel.fs

\ The Forth-side test harness can't drive the keyboard ports, so these
\ tests just exercise the no-keys-held path: angles stay put and quit?
\ returns false.  End-to-end key tests live in test_main_integration.py.

: test-no-keys-quit           quit?           0 assert-eq ;

: test-poll-keys-leaves-yaw
    0 angle-yaw !
    poll-keys
    angle-yaw @  0 assert-eq ;

: test-poll-keys-leaves-pitch
    0 angle-pitch !
    poll-keys
    angle-pitch @  0 assert-eq ;

: test-poll-keys-preserves-stack
    \ Push a sentinel, run poll-keys, check it's still there.
    $1234
    poll-keys
    $1234 assert-eq ;

: test-quit-preserves-stack
    \ ( -- f ): one item left after quit?, with anything below intact.
    $5678
    quit?
    0 assert-eq           \ flag (no keys held)
    $5678 assert-eq ;     \ sentinel still there
