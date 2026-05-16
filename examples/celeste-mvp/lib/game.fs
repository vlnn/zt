require core.fs
require screen.fs
require room.fs
require player.fs
require coin.fs
require spikes.fs
require spring.fs


variable last-painted-deaths
variable last-painted-coins
variable frame-counter
variable advance-requested


$46 constant hud-attr

: emit-digit     ( n -- )    48 + emit ;

: emit-2digit    ( n -- )
    10 u/mod
    emit-digit
    emit-digit ;

: paint-hud-attrs  ( -- )
    hud-attr   1 0 attr-addr   30  rot fill ;

: load-room-1-entities  ( -- )
    28 coin-col   !   21 coin-row   !   224 coin-x   !   168 coin-y   !
    20 spikes-col !   20 spikes-row !   160 spikes-x !   160 spikes-y !
    14 spring-col !   17 spring-row !   112 spring-x !   136 spring-y ! ;

: load-room-2-entities  ( -- )
    15 coin-col   !   16 coin-row   !   120 coin-x   !   128 coin-y   !
    24 spikes-col !   22 spikes-row !   192 spikes-x !   176 spikes-y !
     5 spring-col !   22 spring-row !    40 spring-x !   176 spring-y ! ;

: load-room-entities  ( -- )
    current-room @ 1 = if load-room-1-entities exit then
    current-room @ 2 = if load-room-2-entities exit then ;

: advance-room   ( -- )
    1 current-room +!
    init-room
    load-room-entities
    draw-room
    coin-reset
    spring-reset
    player-reset
    paint-coin
    paint-spikes
    paint-spring
    draw-player ;

: maybe-advance-room  ( -- )
    advance-requested @ 0= if exit then
    0 advance-requested !
    advance-room ;

: paint-altitude ( -- )
    2 0 at-xy ." 100m" ;

: paint-deaths   ( -- )
    22 0 at-xy ." DEATHS:" deaths @ emit-2digit
    deaths @ last-painted-deaths ! ;

: maybe-paint-deaths  ( -- )
    deaths @ last-painted-deaths @ = if exit then
    paint-deaths ;

: paint-coins-count  ( -- )
    10 0 at-xy ." COINS:" coins-count @ emit-2digit
    coins-count @ last-painted-coins ! ;

: maybe-paint-coins  ( -- )
    coins-count @ last-painted-coins @ = if exit then
    paint-coins-count ;

: hud-overdraw?  ( -- flag )
    player-y     @ 8 < if -1 exit then
    player-old-y @ 8 < ;

: maybe-repaint-hud  ( -- )
    hud-overdraw? 0= if exit then
    paint-hud-attrs
    paint-altitude
    -1 last-painted-deaths !
    -1 last-painted-coins ! ;

: init-game      ( -- )
    0 7 cls
    1 current-room !
    init-room
    load-room-entities
    draw-room
    player-reset
    coin-reset
    spikes-reset
    spring-reset
    paint-altitude
    paint-hud-attrs
    -1 last-painted-deaths !
    paint-deaths
    -1 last-painted-coins !
    paint-coins-count
    0 frame-counter !
    0 advance-requested !
    lock-sprites
    paint-coin
    paint-spikes
    paint-spring
    draw-player ;

: game-step      ( -- )
    poll-z
    poll-x
    update-facing
    apply-gravity
    apply-velocity
    update-vx
    apply-velocity-x
    tick-coyote
    tick-jump-buffer
    tick-wall-jump-lockout
    tick-dash
    maybe-start-jump
    maybe-cancel-jump
    maybe-start-dash
    maybe-collect-coin
    maybe-bounce-on-spring
    maybe-kill-player
    maybe-advance-room
    save-z
    save-x
    wait-frame
    erase-player
    redraw-room-around-old
    paint-coin
    paint-spikes
    paint-spring
    draw-player
    redraw-room-around-player
    maybe-repaint-hud
    maybe-paint-deaths
    maybe-paint-coins
    save-pos
    1 frame-counter +! ;

: game-loop      ( -- )
    begin game-step again ;

variable skip-title

: paint-title    ( -- )
    0 7 cls
    12 10 at-xy ." CELESTE"
    8  14 at-xy ." PRESS Z TO START" ;

: wait-for-start ( -- )
    begin z-held? until ;

: celeste-mvp    ( -- )
    skip-title @ 0= if
        paint-title
        wait-for-start
    then
    init-game
    game-loop ;
