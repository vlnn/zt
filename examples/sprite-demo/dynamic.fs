\ Sprite dynamics demo: 3 actors, side by side, run forever.
\
\   actor-player   — animated smiley, moved by O (left) and P (right)
\   actor-flier    — single-frame smiley, sine-wave horizontal flight
\   actor-gravity  — ball falling under gravity, bouncing on a "floor"
\
\ Build:  zt build examples/sprite-demo/dynamic.fs -o build/sprite-dynamic.sna
\
\ Controls (in an emulator):
\   O — move player left
\   P — move player right
\
\ The frame loop runs forever — there is no halt.

require lib/animation.fs

\ -- Actor records (compile-time initialized) --------------------------------
\ Layout matches /actor (24 bytes):
\   x(2) y(2) ox(2) oy(2) frames(2) count(1) frame(1) tick(1) rate(1)
\   state(8) spare(2)

\ Player: animated 2-frame smiley. Keyboard-controlled, fixed y.
\ state[0..1] = horizontal speed (pixels per tick). y stays at 24.
create actor-player
    32 , 24 ,                       \ x, y
    32 , 24 ,                       \ ox, oy
    ' smiley-frames ,
    2 c, 0 c, 4 c, 4 c,             \ count=2, frame=0, tick=4, rate=4
    3 , 0 , 0 , 0 ,                 \ state: speed=3 (rest unused)
    0 ,

\ Flier: sine wave. dx=4, base-y=80, phase=0, phase-step=2.
create actor-flier
    8 , 80 ,
    8 , 80 ,
    ' flier-frames ,
    1 c, 0 c, 1 c, 1 c,
    4 , 80 ,                        \ state[0..3]: dx=4, base-y=80
    0 c, 2 c, 0 c, 0 c,             \ state[4..7]: phase=0, step=2, _, _
    0 ,

\ Gravity ball: dx=2, dy=0, gravity=2, floor-y=176.
create actor-gravity
    16 , 16 ,
    16 , 16 ,
    ' ball-frames ,
    1 c, 0 c, 1 c, 1 c,
    2 , 0 , 2 , 176 ,               \ state: dx, dy, gravity, floor-y
    0 ,

\ -- Per-actor stepping ------------------------------------------------------

: step-player
    actor-player dup actor-pre-step
    dup player-control
    actor-post-step ;

: step-flier
    actor-flier dup actor-pre-step
    dup sine-flier
    actor-post-step ;

: step-gravity
    actor-gravity dup actor-pre-step
    dup gravity-bounce
    actor-post-step ;

: step-all
    step-player
    step-flier
    step-gravity ;

\ -- main --------------------------------------------------------------------
\ Forever loop. To bound execution (e.g. for tests), wrap the body in a
\ counted DO/LOOP and HALT after; keeping interrupts disabled (no
\ UNLOCK-SPRITES) lets HALT actually stop the simulator.

: main
    7 0 cls
    lock-sprites
    begin
        step-all
    again ;
