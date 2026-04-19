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

variable alive

: die            ( -- )   explosion  0 alive ! ;

: award-bonus    ( -- )   level-bonus@ score +! ;

: reward-level   ( -- )   award-bonus   100 score +! ;
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
    reset-ti ;

: step-once      ( -- )
    wait-frame
    1 ti +!
    map-blow-due? if blow-map-away then
    maybe-spawn-spreader
    spreader-step
    try-move 0= if exit then
    click
    old-xy erase-at
    maybe-rescue
    player-xy empty? 0= if handle-collision exit then
    player-xy player-at
    update-hud
    won? if win exit then
    snapshot-pos
    record-step
    bug-step
    player-hit-bug? if die exit then
    4 throttle ;

: play-loop      ( -- )
    1 alive !
    begin alive @ while step-once repeat ;

: place-actors-for-level  ( -- )
    has-bill? if pick-bill place-bill else pick-damsels then ;

: init-level     ( -- )
    apply-level-colors
    board-init
    build-fences
    level-mines@ scatter-mines
    place-actors-for-level
    bug-reset
    0 spreader-active !
    reset-ti
    player-reset
    trail-setup
    draw-hud
    player-xy player-at ;

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

: continue-or-restart ( -- )
    won? if
        has-bill? if bill-rescued exit then
        advance-level exit
    then
    check-hiscore
    reset-for-new-game ;

: init-game      ( -- )
    setup-keys
    hi-reset
    0 score !
    1 level-no !
    1 seed! ;
