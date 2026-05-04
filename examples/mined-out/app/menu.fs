\ Level-select prompt.  Shown after the first death once the player
\ has unlocked level 2 or higher; lets them resume at any unlocked
\ level rather than starting from 1 every time.  The 'I' key
\ re-shows the intro sequence as an escape hatch for the rules.

require core.fs
require input.fs
require screen.fs

require state.fs
require title.fs


\ Key validation
\ ──────────────
\ valid-level-key? accepts ASCII '1'..'9' but only up to the unlocked
\ maximum.  intro-key? matches both upper- and lowercase 'I'.

: key->level       ( c -- n )       48 - ;

: valid-level-key? ( c -- flag )
    dup 49 <  if drop 0 exit then
    dup 57 >  if drop 0 exit then
    key->level max-level-reached @ > 0= ;

: intro-key?       ( c -- flag )
    dup 73 =  swap 105 =  or ;


\ Banner and key reading
\ ──────────────────────
\ wait-real-key drains stale keystrokes (carried over from the
\ previous death) before blocking, so the first valid key in a fresh
\ press is what gets read.

: apply-level-select ( level -- )
    level-no !
    level-bonus@ dup score ! initial-bonus-pending ! ;

: level-select-banner ( -- )
    0 10 at-xy  ." start at level 1.."  max-level-reached @ .
    0 12 at-xy  ." (I for instructions)     " ;

: wait-real-key    ( -- c )
    begin
        drain-keys wait-key
        dup 0=
    while drop repeat ;


\ The interaction
\ ───────────────
\ try-read-level returns either a chosen level or -1 (intro request
\ or invalid key).  read-valid-level retries until it gets a valid
\ digit; select-level is the public entry point that draws the
\ banner, reads a level, and applies it.

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
