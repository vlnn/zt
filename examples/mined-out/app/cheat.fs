\ app/cheat.fs — hidden cheat: two alternating horizontal moves (L,R or
\ R,L) reveal every mine via show-all-mines. Re-armed at each level start
\ and whenever the map gets blown away.

require core.fs

require state.fs
require board.fs

2 constant cheat-target

variable cheat-state
variable cheat-last-dx

\ clear the cheat progress and last direction
: cheat-reset      ( -- )        0 cheat-state !  0 cheat-last-dx ! ;

\ true if the cheat has just fired this level
: cheat-fired?     ( -- flag )   cheat-state @ cheat-target = ;
\ true if the cheat is locked out for the rest of the level
: cheat-locked?    ( -- flag )   cheat-state @ 0 < ;

\ true if the cheat is still accepting input (armed but not yet fired)
: cheat-watching?  ( -- flag )
    cheat-state @  dup 0 <  0=
                   swap cheat-target <  and ;

\ reveal every mine and mark the cheat as fired
: cheat-fire       ( -- )        show-all-mines  cheat-target cheat-state ! ;
\ disable the cheat for the rest of the level
: cheat-lock       ( -- )        -1 cheat-state ! ;

\ store progress, firing the cheat once it reaches the target
: cheat-advance-to  ( progress -- )
    dup cheat-target = if drop cheat-fire exit then
    cheat-state ! ;

\ feed one horizontal step to the cheat: alternate dx advances, repeats lock
: cheat-step-horizontal  ( dx -- )
    dup 0= if drop exit then
    dup cheat-last-dx @ = if
        drop cheat-lock
    else
        cheat-last-dx !
        cheat-state @ 1+ cheat-advance-to
    then ;

\ feed a player movement (dx, dy) to the cheat detector
: cheat-observe    ( dx dy -- )
    cheat-watching? 0= if 2drop exit then
    dup if 2drop cheat-lock exit then
    drop cheat-step-horizontal ;
