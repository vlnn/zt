\ HUD rendering, proximity beep, trail recording, action replay, and
\ the per-level intro banners.  The trail buffer doubles as data for
\ the bug and wind effects (see actors.fs); recording every step is
\ what makes the post-level replay possible.

require core.fs
require screen.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs
require actors.fs


\ The status line
\ ───────────────
\ One row at the top of the screen showing the adjacency count,
\ score, and current level.  update-hud is the per-frame entry: it
\ also plays the proximity beep, since the audible cue is part of
\ the HUD experience.

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


\ The trail
\ ─────────
\ A 1024-cell circular buffer of packed (col, row) pairs.  Used by
\ the bug and wind to chase the player, and by the action replay to
\ play back the round.  Cleared at the start of every level.

1024 constant trail-cells
create trail-buf  2048 allot

: trail-setup    ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

: record-step    ( -- )        player-xy pack-xy trail-push ;


\ Action replay
\ ─────────────
\ After a death or win, replay the player's path step by step.  The
\ player can hold S to slow it down or E to skip the rest.  The
\ banner is overwritten on each tick so it stays in place during
\ the playback.

: slow-held?     ( -- flag )   83 pressed? ;
: end-held?      ( -- flag )   69 pressed? ;

: throttle       ( frames -- ) 0 do wait-frame loop ;

: replay-frames  ( -- n )      slow-held? if 10 else 3 then ;
: replay-delay   ( -- )        replay-frames throttle ;

: replay-step    ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

: at-banner      ( -- )        0 banner-row at-xy ;

: replay-banner  ( -- )
    at-banner  ." replay (S=slow E=end)         " ;

: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do
        end-held? if leave then
        i replay-step
    loop ;


\ Per-level banners
\ ─────────────────
\ Each new feature gets a one-line introduction the first time the
\ player meets it.  show-level-intro picks the right one based on
\ level-no, falling through to nothing on levels with no new
\ feature.  initial-bonus-pending suppresses the intro on the first
\ frame after a level pick — show-initial-bonus runs in its place.

: clear-banner-row  ( -- )
    at-banner  32 0 do space loop ;

: intro-level-2  ( -- )   at-banner  ." rescue the damsels!" ;
: intro-level-3  ( -- )   at-banner  ." watch out - spreaders!" ;
: intro-level-4  ( -- )   at-banner  ." a bug stalks your trail" ;
: intro-level-5  ( -- )   at-banner  ." your map may blow away" ;
: intro-level-8  ( -- )   at-banner  ." gap is closed - hug three mines" ;
: intro-level-9  ( -- )   at-banner  ." rescue bill from the chamber" ;

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
    at-banner  ." initial bonus = "  .
    0 initial-bonus-pending ! ;
