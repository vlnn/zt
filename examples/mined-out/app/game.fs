\ app/game.fs — top-level game flow: init, step-once, play-loop,
\ level completion, death, and win.

require core.fs
require screen.fs
require hiscore.fs

require state.fs
require sounds.fs
require board.fs
require actors.fs
require hud.fs
require menu.fs

variable alive

: die            ( -- )   explosion  0 alive ! ;

: speed-bonus    ( -- n )
    2000 ti @ -  50 /  5 *   50 max   level-no @ * ;

: reward-level   ( -- )   speed-bonus score +! ;
: reward-bill    ( -- )   2000 score +! ;

: win            ( -- )
    fanfare
    has-bill? if reward-bill else reward-level then
    0 alive ! ;

: reveal-player-cell  ( -- )
    player-xy fence? 0= if player-xy mine-at then ;

: handle-collision  ( -- )
    reveal-player-cell die ;

: won?           ( -- flag )
    has-bill? if player-xy bill? else prow @ 0= then ;

: map-blown-banner  ( -- )
    0 21 at-xy  ." your map has blown away! (shame)" ;

: blow-map-away  ( -- )
    map-blown-banner
    hide-all-mines
    cheat-reset
    reset-ti ;

: maybe-open-gap  ( -- )
    has-closed-gap? 0= if exit then
    gap-open?          if exit then
    adj-count 3 = if open-top-gap gap-chirp then ;

: tick-world     ( -- )
    1 ti +!
    map-blow-due? if blow-map-away then
    maybe-spawn-spreader
    spreader-step ;

: after-player-move  ( -- )
    click
    old-xy erase-at
    maybe-rescue
    player-xy empty? 0= if handle-collision exit then
    player-xy player-at
    update-hud
    maybe-open-gap
    won? if win exit then
    snapshot-pos
    record-step
    bug-step
    player-hit-bug? if die exit then ;

: step-once      ( -- )
    wait-frame
    tick-world
    try-move 0= if exit then
    after-player-move
    alive @ if 4 throttle then ;

: play-loop      ( -- )
    1 alive !
    begin alive @ while step-once repeat ;

: place-actors-for-level  ( -- )
    has-bill? if pick-bill place-bill else pick-damsels then ;

: init-level     ( -- )
    apply-level-colors
    board-init
    build-fences
    has-closed-gap? if close-top-gap then
    level-mines@ scatter-mines
    place-actors-for-level

    bug-reset
    0 spreader-active !
    reset-ti
    cheat-reset

    player-reset
    trail-setup

    draw-hud
    player-xy player-at
    show-level-intro
    show-initial-bonus ;

: end-of-level   ( -- )
    show-all-mines
    action-replay
    50 throttle ;

: record-hiscore      ( -- )   hi-name read-initials  score @ hi-set-score ;
: check-hiscore       ( -- )   score @ hi-beats? if record-hiscore then ;

: reset-for-new-game  ( -- )   0 score !  1 level-no ! ;

: bill-banner         ( -- )   0 21 at-xy  ." rescued bill! +2000 points     " ;

: bill-rescued        ( -- )
    bill-banner
    check-hiscore
    reset-for-new-game ;

: should-select-level?  ( -- flag )   max-level-reached @ 2 < 0= ;

: continue-or-restart ( -- )
    drain-keys
    won? if
        has-bill? if bill-rescued exit then
        advance-level exit
    then
    check-hiscore
    reset-for-new-game
    should-select-level? if select-level then ;

: init-game      ( -- )
    hi-reset
    1 max-level-reached !
    0 initial-bonus-pending !
    0 score !
    1 level-no !
    1 seed! ;
