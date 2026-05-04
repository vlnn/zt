\ Hidden cheat: two alternating horizontal moves (L-R or R-L) reveal
\ every mine via show-all-mines.  Re-armed at each level start and
\ whenever the map gets blown away — so on a map-blow level you can
\ recover by performing the same gesture again.  Any vertical move,
\ or repeating the same horizontal direction twice, locks the cheat
\ for the rest of the level.

require core.fs

require state.fs
require board.fs

2 constant cheat-target

variable cheat-state
variable cheat-last-dx


\ State predicates
\ ────────────────
\ cheat-state holds progress (0, 1, target = fired, or -1 = locked).
\ Three predicates check each phase so the observer below can branch
\ readably without manually decoding the state byte.

: cheat-reset      ( -- )        0 cheat-state !  0 cheat-last-dx ! ;

: cheat-fired?     ( -- flag )   cheat-state @ cheat-target = ;
: cheat-locked?    ( -- flag )   cheat-state @ 0 < ;

: cheat-watching?  ( -- flag )
    cheat-state @  dup 0 <  0=
                   swap cheat-target <  and ;


\ Transitions
\ ───────────
\ cheat-fire is the success path; cheat-lock disables for the rest of
\ the level.  cheat-advance-to commits a new progress value, firing
\ when it reaches the target.

: cheat-fire       ( -- )        show-all-mines  cheat-target cheat-state ! ;
: cheat-lock       ( -- )        -1 cheat-state ! ;

: cheat-advance-to  ( progress -- )
    dup cheat-target = if drop cheat-fire exit then
    cheat-state ! ;


\ Observer
\ ────────
\ cheat-observe is fed every player movement.  Vertical moves
\ immediately lock; a horizontal move advances if it differs from the
\ previous direction, otherwise it locks.  Once the level's first
\ horizontal move sets cheat-last-dx, the second has to be opposite
\ to count.

: cheat-step-horizontal  ( dx -- )
    dup 0= if drop exit then
    dup cheat-last-dx @ = if
        drop cheat-lock
    else
        cheat-last-dx !
        cheat-state @ 1+ cheat-advance-to
    then ;

: cheat-observe    ( dx dy -- )
    cheat-watching? 0= if 2drop exit then
    dup if 2drop cheat-lock exit then
    drop cheat-step-horizontal ;
