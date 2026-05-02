include test-lib.fs
include ay.fs

\ -- constants -------------------------------------------------------------

: test-ay-mixer-tones-only-value
    ay-mixer-tones-only            $38 assert-eq ;

: test-ay-volume-max-value
    ay-volume-max                  $0F assert-eq ;

: test-ay-volume-mute-value
    ay-volume-mute                 0 assert-eq ;

\ -- ay-set: consumes (val reg) --------------------------------------------

: test-ay-set-consumes-two
    99  $0F 7 ay-set
    99 assert-eq ;

\ -- ay-mixer!: consumes (bits) --------------------------------------------

: test-ay-mixer-consumes-one
    99  $38 ay-mixer!
    99 assert-eq ;

\ -- ay-noise!: consumes (period) ------------------------------------------

: test-ay-noise-consumes-one
    99  16 ay-noise!
    99 assert-eq ;

\ -- ay-tone-{a,b,c}!: each consumes (period) ------------------------------

: test-ay-tone-a-consumes-one
    99  424 ay-tone-a!
    99 assert-eq ;

: test-ay-tone-b-consumes-one
    99  377 ay-tone-b!
    99 assert-eq ;

: test-ay-tone-c-consumes-one
    99  336 ay-tone-c!
    99 assert-eq ;

\ -- ay-vol-{a,b,c}!: each consumes (level) --------------------------------

: test-ay-vol-a-consumes-one
    99  $0F ay-vol-a!
    99 assert-eq ;

: test-ay-vol-b-consumes-one
    99  $08 ay-vol-b!
    99 assert-eq ;

: test-ay-vol-c-consumes-one
    99  0 ay-vol-c!
    99 assert-eq ;
