\ app/hud.fs — HUD rendering, proximity beep, trail recording, action replay.

require core.fs
require screen.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs
require actors.fs

: two-digits     ( n -- )
    dup 10 < if 48 emit then . ;

: draw-hud       ( -- )
    0 0 at-xy
    ." adj:"   adj-count two-digits
    ."   score:" score @ .
    ."   lvl:"   level-no @ . ;

: update-hud     ( -- )
    adj-count proximity
    draw-hud ;

1024 constant trail-cells
create trail-buf  2048 allot

: trail-setup    ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

: record-step    ( -- )        player-xy pack-xy trail-push ;

: slow-held?     ( -- flag )   83 pressed? ;
: end-held?      ( -- flag )   69 pressed? ;

: replay-frames  ( -- n )      slow-held? if 10 else 3 then ;
: replay-delay   ( -- )        replay-frames 0 do wait-frame loop ;
: throttle       ( frames -- ) 0 do wait-frame loop ;

: replay-step    ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

: replay-banner  ( -- )
    0 banner-row at-xy  ." replay (S=slow E=end)         " ;

: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do
        end-held? if leave then
        i replay-step
    loop ;

: clear-banner-row  ( -- )
    0 banner-row at-xy  32 0 do space loop ;

: intro-level-2  ( -- )   0 banner-row at-xy  ." rescue the damsels!" ;
: intro-level-3  ( -- )   0 banner-row at-xy  ." watch out - spreaders!" ;
: intro-level-4  ( -- )   0 banner-row at-xy  ." a bug stalks your trail" ;
: intro-level-5  ( -- )   0 banner-row at-xy  ." your map may blow away" ;
: intro-level-8  ( -- )   0 banner-row at-xy  ." gap is closed - hug three mines" ;
: intro-level-9  ( -- )   0 banner-row at-xy  ." rescue bill from the chamber" ;

: show-level-intro  ( -- )
    initial-bonus-pending @ if exit then
    clear-banner-row
    level-no @
    dup 2 = if drop intro-level-2 exit then
    dup 3 = if drop intro-level-3 exit then
    dup 4 = if drop intro-level-4 exit then
    dup 5 = if drop intro-level-5 exit then
    dup 8 = if drop intro-level-8 exit then
    dup 9 = if drop intro-level-9 exit then
    drop ;

: show-initial-bonus  ( -- )
    initial-bonus-pending @ dup 0= if drop exit then
    0 banner-row at-xy  ." initial bonus = "  .
    0 initial-bonus-pending ! ;
