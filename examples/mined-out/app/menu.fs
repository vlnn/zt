\ app/menu.fs — level-select prompt and its pure-logic pieces.

require core.fs
require input.fs
require screen.fs

require state.fs
require title.fs

\ convert ASCII digit 0..9 to its numeric value
: key->level       ( c -- n )       48 - ;

\ true if c is a digit 1..9 not above the unlocked maximum
: valid-level-key? ( c -- flag )
    dup 49 <  if drop 0 exit then
    dup 57 >  if drop 0 exit then
    key->level max-level-reached @ > 0= ;

\ commit the chosen level: set level number, score and pending bonus
: apply-level-select ( level -- )
    level-no !
    level-bonus@ dup score ! initial-bonus-pending ! ;

\ draw the "start at level 1..N" prompt
: level-select-banner ( -- )
    0 10 at-xy  ." start at level 1.."  max-level-reached @ .
    0 12 at-xy  ." (I for instructions)     " ;

\ true if c is upper or lower case 'I'
: intro-key?       ( c -- flag )
    dup 73 =  swap 105 =  or ;

\ wait for the next real (non-zero) keypress, draining stale ones first
: wait-real-key    ( -- c )
    begin
        drain-keys wait-key
        dup 0=
    while drop repeat ;

\ read one menu key: returns level, or -1 on intro request or invalid input
: try-read-level   ( -- level | -1 )
    wait-real-key
    dup intro-key? if drop show-intro level-select-banner -1 exit then
    dup valid-level-key? if key->level else drop -1 then ;

\ keep prompting until a valid level digit is pressed, then return it
: read-valid-level ( -- level )
    begin try-read-level dup 0 < 0= until ;

\ run the full level-select interaction
: select-level     ( -- )
    level-select-banner
    read-valid-level
    apply-level-select ;
