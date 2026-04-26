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

\ play the explosion sound and mark the player dead
: die            ( -- )   explosion  0 alive ! ;

\ time-bonus reward, weighted by the current level
: speed-bonus    ( -- n )
    2000 ti @ -  50 /  5 *   50 max   level-no @ * ;

\ award the level-completion bonus
: reward-level   ( -- )   speed-bonus score +! ;
\ award the fixed bonus for rescuing Bill
: reward-bill    ( -- )   2000 score +! ;

\ player has reached the goal: play fanfare, award bonus, end the level
: win            ( -- )
    fanfare
    has-bill? if reward-bill else reward-level then
    0 alive ! ;

\ on death: keep fence cells blank, reveal a mine elsewhere
: reveal-player-cell  ( -- )
    player-xy  2dup fence? if 2drop else mine-at then ;

\ handle stepping onto a mine: reveal the cell and die
: handle-collision  ( -- )
    reveal-player-cell die ;

\ true if the level's goal has been met
: won?           ( -- flag )
    has-bill? if player-xy bill? else prow @ 0= then ;

\ banner shown when the level's map blows away
: map-blown-banner  ( -- )
    0 banner-row at-xy  ." your map has blown away! (shame)" ;

\ erase the visible map (level 5+): banner, reset cheat and timer
: blow-map-away  ( -- )
    map-blown-banner
    cheat-reset
    reset-ti ;

\ on the closed-gap level, open the top gap once standing on three mines
: maybe-open-gap  ( -- )
    has-closed-gap? 0= if exit then
    gap-open?          if exit then
    adj-count 3 = if open-top-gap gap-chirp then ;

\ advance world state by one tick: ageing, map blow, spreader
: tick-world     ( -- )
    1 ti +!
    map-blow-due? if blow-map-away then
    maybe-spawn-spreader
    spreader-step ;

\ post-process effects after a successful player move
: after-player-move  ( -- )
    click
    old-xy trail-at
    maybe-rescue
    player-xy empty? 0= if handle-collision exit then
    player-xy player-at
    update-hud
    maybe-open-gap
    won? if win exit then
    snapshot-pos
    record-step
    bug-step
    player-hit-bug?  if die exit then ;

\ advance the wind effect by one tick if it is due, killing player on push into mine
: tick-wind      ( -- )
    wind-due? 0= if exit then
    wind-step
    player-hit-by-wind? if die then ;

\ run a single game tick: input, world, wind, throttle
: step-once      ( -- )
    wait-frame
    tick-world
    try-move if after-player-move then
    alive @ 0= if exit then
    tick-wind
    alive @ if 4 throttle then ;

\ run the per-frame game loop until the player dies or wins
: play-loop      ( -- )
    1 alive !
    begin alive @ while step-once repeat ;

\ place either Bill or the damsels, depending on the current level
: place-actors-for-level  ( -- )
    has-bill? if pick-bill place-bill else pick-damsels then ;

\ set up everything for a fresh level (board, actors, HUD, banner)
: init-level     ( -- )
    apply-level-colors
    board-init
    build-fences
    has-closed-gap? if close-top-gap then
    level-mines@ scatter-mines
    place-actors-for-level

    bug-reset
    wind-reset
    0 spreader-active !
    reset-ti
    cheat-reset

    player-reset
    trail-setup

    draw-hud
    player-xy player-at
    show-level-intro
    show-initial-bonus ;

\ post-level: reveal mines, replay the player's path, settle
: end-of-level   ( -- )
    show-all-mines
    action-replay
    50 throttle ;

\ prompt for high-score initials and store the new score
: record-hiscore      ( -- )   hi-name read-initials  score @ hi-set-score ;
\ if score beats the current record, record a new high score
: check-hiscore       ( -- )   score @ hi-beats? if record-hiscore then ;

\ reset score and level for a new game
: reset-for-new-game  ( -- )   0 score !  1 level-no ! ;

\ banner celebrating Bill's rescue
: bill-banner         ( -- )   0 banner-row at-xy  ." rescued bill! +2000 points     " ;

\ Bill rescued: banner, hi-score check, reset for next game
: bill-rescued        ( -- )
    bill-banner
    check-hiscore
    reset-for-new-game ;

\ true once the player has unlocked enough levels for level select
: should-select-level?  ( -- flag )   max-level-reached @ 2 < 0= ;

\ post-level transition: advance, restart, or offer level select
: continue-or-restart ( -- )
    drain-keys
    won? if
        has-bill? if bill-rescued exit then
        advance-level exit
    then
    check-hiscore
    reset-for-new-game
    should-select-level? if select-level then ;

\ first-time setup of the entire game: hi-score, max level, RNG
: init-game      ( -- )
    hi-reset
    1 max-level-reached !
    0 initial-bonus-pending !
    0 score !
    1 level-no !
    1 seed! ;
