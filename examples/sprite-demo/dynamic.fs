\ Three actors animated side by side, run forever.  The player is a
\ keyboard-controlled animated smiley; the flier is a smiley sliding
\ horizontally with a vertical sine wave; the gravity ball falls,
\ accelerates, and bounces off an invisible floor.  Together they
\ exercise every part of the actor framework in lib/animation.fs.
\
\ Controls: O moves the player left, P moves it right.  No HALT —
\ the loop is open-ended; an emulator just keeps running it.
\
\ Build:  zt build examples/sprite-demo/dynamic.fs -o build/sprite-dynamic.sna

require lib/animation.fs


\ Actor records
\ ─────────────
\ Each `create` reserves 24 bytes and initialises every field.  Layout
\ comes from /actor in animation.fs: position cells, previous-position
\ cells, the frames-table xt, count/frame/tick/rate bytes, then 8
\ bytes of trajectory-private state.  The state slots mean different
\ things to different trajectories — see the comments above each.

\ Player: animated 2-frame smiley, fixed y = 24, state[0..1] = speed.
create actor-player
    32 , 24 ,
    32 , 24 ,
    ' smiley-frames ,
    2 c, 0 c, 4 c, 4 c,
    3 , 0 , 0 , 0 ,
    0 ,

\ Flier: state[0..3] = dx + base-y; state[4..5] = phase + step.
create actor-flier
    8 , 80 ,
    8 , 80 ,
    ' flier-frames ,
    1 c, 0 c, 1 c, 1 c,
    4 , 80 ,
    0 c, 2 c, 0 c, 0 c,
    0 ,

\ Gravity ball: state = dx, dy, gravity, floor-y.
create actor-gravity
    16 , 16 ,
    16 , 16 ,
    ' ball-frames ,
    1 c, 0 c, 1 c, 1 c,
    2 , 0 , 2 , 176 ,
    0 ,


\ Per-actor stepping
\ ──────────────────
\ Every step word follows the same shape: erase, run a trajectory,
\ then tick + draw + save-position.  actor-pre-step / actor-post-step
\ from animation.fs encapsulate the boilerplate; only the trajectory
\ in the middle differs from actor to actor.

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


\ Main loop
\ ─────────
\ Forever loop with no halt.  Interrupts stay disabled (lock-sprites
\ is not paired with unlock-sprites), so the simulator can be stopped
\ cleanly from the outside; for a real frame-rate program you'd want
\ to unlock and synchronise to the ULA.

: main
    7 0 cls
    lock-sprites
    begin
        step-all
    again ;
