\ app/cheat.fs — hidden cheat: two alternating horizontal moves (L,R or
\ R,L) reveal every mine via show-all-mines. Re-armed at each level start
\ and whenever the map gets blown away.

require core.fs

require state.fs
require board.fs

2 constant cheat-target

variable cheat-state
variable cheat-last-dx

: cheat-reset      ( -- )        0 cheat-state !  0 cheat-last-dx ! ;

: cheat-fired?     ( -- flag )   cheat-state @ cheat-target = ;
: cheat-locked?    ( -- flag )   cheat-state @ 0 < ;

: cheat-watching?  ( -- flag )
    cheat-state @  dup 0 <  0=
                   swap cheat-target <  and ;

: cheat-fire       ( -- )        show-all-mines  cheat-target cheat-state ! ;
: cheat-lock       ( -- )        -1 cheat-state ! ;

: cheat-advance-to  ( progress -- )
    dup cheat-target = if drop cheat-fire exit then
    cheat-state ! ;

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
