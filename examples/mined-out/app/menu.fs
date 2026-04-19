\ app/menu.fs — level-select prompt and its pure-logic pieces.

require core.fs
require input.fs
require screen.fs

require state.fs
require title.fs

: key->level       ( c -- n )       48 - ;

: valid-level-key? ( c -- flag )
    dup 49 <  if drop 0 exit then
    dup 57 >  if drop 0 exit then
    key->level max-level-reached @ > 0= ;

: apply-level-select ( level -- )
    level-no !
    level-bonus@ dup score ! initial-bonus-pending ! ;

: level-select-banner ( -- )
    0 10 at-xy  ." start at level 1.."  max-level-reached @ .
    0 12 at-xy  ." (I for instructions)     " ;

: intro-key?       ( c -- flag )
    dup 73 =  swap 105 =  or ;

: wait-real-key    ( -- c )
    begin
        drain-keys wait-key
        dup 0=
    while drop repeat ;

: try-read-level   ( -- level | -1 )
    wait-real-key
    dup intro-key? if drop show-intro level-select-banner -1 exit then
    dup valid-level-key? if key->level else drop -1 then ;

: read-valid-level ( -- level )
    begin try-read-level dup 0 < 0= until ;

: select-level     ( -- )
    level-select-banner
    read-valid-level
    apply-level-select ;
