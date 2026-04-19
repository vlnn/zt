include test-lib.fs
include input.fs

: test-dir-flags-neutral-dx
    0 0 0 0 dir-from-flags  drop 0 assert-eq ;

: test-dir-flags-neutral-dy
    0 0 0 0 dir-from-flags  nip  0 assert-eq ;

: test-dir-flags-left-dx
    1 0 0 0 dir-from-flags  drop -1 assert-eq ;

: test-dir-flags-left-dy-zero
    1 0 0 0 dir-from-flags  nip   0 assert-eq ;

: test-dir-flags-right-dx
    0 1 0 0 dir-from-flags  drop  1 assert-eq ;

: test-dir-flags-up-dy
    0 0 1 0 dir-from-flags  nip  -1 assert-eq ;

: test-dir-flags-down-dy
    0 0 0 1 dir-from-flags  nip   1 assert-eq ;

: test-dir-flags-leftup-dx
    1 0 1 0 dir-from-flags  drop -1 assert-eq ;

: test-dir-flags-leftup-dy
    1 0 1 0 dir-from-flags  nip  -1 assert-eq ;

: test-dir-flags-rightdown-dx
    0 1 0 1 dir-from-flags  drop  1 assert-eq ;

: test-dir-flags-rightdown-dy
    0 1 0 1 dir-from-flags  nip   1 assert-eq ;

: test-dir-flags-opposing-dx-cancels
    1 1 0 0 dir-from-flags  drop  0 assert-eq ;

: test-dir-flags-opposing-dy-cancels
    0 0 1 1 dir-from-flags  nip   0 assert-eq ;

: test-set-keys-stores-left
    54 55 56 57 set-keys!  key-left  @ 54 assert-eq ;

: test-set-keys-stores-right
    54 55 56 57 set-keys!  key-right @ 55 assert-eq ;

: test-set-keys-stores-up
    54 55 56 57 set-keys!  key-up    @ 56 assert-eq ;

: test-set-keys-stores-down
    54 55 56 57 set-keys!  key-down  @ 57 assert-eq ;
