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

: replay-delay   ( -- )        3 0 do wait-frame loop ;
: throttle       ( frames -- ) 0 do wait-frame loop ;

: replay-step    ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

: replay-banner  ( -- )
    0 21 at-xy  ." action replay                   " ;

: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do i replay-step loop ;
