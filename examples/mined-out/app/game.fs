\ app/game.fs — top-level game flow: init, step-once, play-loop,
\ level completion, death, and win.

require core.fs
require screen.fs

require state.fs
require sounds.fs
require board.fs
require actors.fs
require hud.fs

variable alive

: die            ( -- )   explosion  0 alive ! ;

: award-bonus    ( -- )   level-bonus@ score +! ;

: win            ( -- )   fanfare award-bonus 100 score +!  0 alive ! ;

: reveal-player-cell  ( -- )
    player-xy fence? 0= if player-xy mine-at then ;

: handle-collision  ( -- )
    reveal-player-cell die ;

: won?           ( -- flag )     px @ 0= ;

: step-once      ( -- )
    wait-frame
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

: init-level     ( -- )
    apply-level-colors
    board-init
    build-fences
    level-mines@ scatter-mines
    pick-damsels
    bug-reset
    0 spreader-active !
    player-reset
    trail-setup
    draw-hud
    player-xy player-at ;

: end-of-level   ( -- )
    show-all-mines
    action-replay
    50 throttle ;

: init-game      ( -- )
    setup-keys
    0 score !
    1 level-no !
    1 seed! ;
