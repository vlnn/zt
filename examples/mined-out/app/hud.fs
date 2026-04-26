\ app/hud.fs — HUD rendering, proximity beep, trail recording, action replay.

require core.fs
require screen.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs
require actors.fs

\ print n with a leading zero if it is below 10
: two-digits     ( n -- )
    dup 10 < if 48 emit then . ;

\ paint the top-of-screen status line: adjacency, score, level
: draw-hud       ( -- )
    0 0 at-xy
    ." adj:"   adj-count two-digits
    ."   score:" score @ .
    ."   lvl:"   level-no @ . ;

\ play the proximity beep and refresh the HUD
: update-hud     ( -- )
    adj-count proximity
    draw-hud ;

1024 constant trail-cells
create trail-buf  2048 allot

\ bind and clear the trail buffer used by the action-replay
: trail-setup    ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

\ append the player's current position to the trail
: record-step    ( -- )        player-xy pack-xy trail-push ;

\ true while the slow-replay key (S) is held
: slow-held?     ( -- flag )   83 pressed? ;
\ true while the end-replay key (E) is held
: end-held?      ( -- flag )   69 pressed? ;

\ block for the given number of frames
: throttle       ( frames -- ) 0 do wait-frame loop ;

\ frames per replay step: slower while S is held
: replay-frames  ( -- n )      slow-held? if 10 else 3 then ;
\ throttle one replay step
: replay-delay   ( -- )        replay-frames throttle ;

\ replay the i-th recorded step: draw player, pause, then erase
: replay-step    ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

\ position cursor at the start of the banner row
: at-banner      ( -- )        0 banner-row at-xy ;

\ print the action-replay banner with the slow/end key hints
: replay-banner  ( -- )
    at-banner  ." replay (S=slow E=end)         " ;

\ play back the recorded trail, skipping the rest if E is held
: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do
        end-held? if leave then
        i replay-step
    loop ;

\ blank the banner row
: clear-banner-row  ( -- )
    at-banner  32 0 do space loop ;

\ banner shown at the start of level 2
: intro-level-2  ( -- )   at-banner  ." rescue the damsels!" ;
\ banner shown at the start of level 3
: intro-level-3  ( -- )   at-banner  ." watch out - spreaders!" ;
\ banner shown at the start of level 4
: intro-level-4  ( -- )   at-banner  ." a bug stalks your trail" ;
\ banner shown at the start of level 5
: intro-level-5  ( -- )   at-banner  ." your map may blow away" ;
\ banner shown at the start of level 8
: intro-level-8  ( -- )   at-banner  ." gap is closed - hug three mines" ;
\ banner shown at the start of level 9
: intro-level-9  ( -- )   at-banner  ." rescue bill from the chamber" ;

\ pick the right intro banner for the current level (or do nothing)
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

\ if a starting bonus is queued, print it and clear the flag
: show-initial-bonus  ( -- )
    initial-bonus-pending @ dup 0= if drop exit then
    at-banner  ." initial bonus = "  .
    0 initial-bonus-pending ! ;
