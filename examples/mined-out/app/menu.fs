\ app/menu.fs — level-select prompt and its pure-logic pieces.
\
\ Pure pieces are unit-tested; the interactive `select-level` wraps them
\ around wait-key, which can only be exercised in the real runtime.

require core.fs
require input.fs
require screen.fs

require state.fs

: key->level       ( c -- n )       48 - ;

: valid-level-key? ( c -- flag )
    dup 49 <  if drop 0 exit then           \ below '1'
    dup 57 >  if drop 0 exit then           \ above '9'
    key->level max-level-reached @ > 0= ;   \ level <= max? 

: apply-level-select ( level -- )
    level-no !
    level-bonus@ score ! ;

: level-select-banner ( -- )
    0 10 at-xy  ." start at level 1.."  max-level-reached @ . ;

: try-read-level   ( -- level | -1 )
    wait-key
    dup valid-level-key? if key->level else drop -1 then ;

: read-valid-level ( -- level )
    begin try-read-level dup 0 < 0= until ;

: select-level     ( -- )
    level-select-banner
    read-valid-level
    apply-level-select ;
