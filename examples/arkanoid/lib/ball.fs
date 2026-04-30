\ Ball physics for arkanoid.
\
\ State:
\   ball-x, ball-y    pixel position of the top-left of the 8x8 sprite
\   ball-ox, ball-oy  prior position (for cell-restore in game.fs)
\   ball-dx, ball-dy  per-frame velocity. dy is fixed at +/-2; dx ranges
\                     -3..+3 set by paddle hit zone + paddle velocity.
\   ball-lost         non-zero when the ball has fallen below paddle row.
\
\ Per-frame role: ball-paint (called at the start of game-step) draws the
\ ball at (ball-x, ball-y) and snapshots that into (ball-ox, ball-oy);
\ ball-physics (called later in the same frame) advances position and
\ resolves collisions, possibly setting ball-lost.

require core.fs
require sprites.fs
require bricks.fs
require paddle.fs
require score.fs

variable ball-x
variable ball-y
variable ball-ox
variable ball-oy
variable ball-dx
variable ball-dy
variable ball-lost

128 constant ball-start-x
160 constant ball-start-y
2   constant ball-init-dx
-2  constant ball-init-dy

\ Bounds. ball-min-x / ball-max-x keep the 8-pixel-wide ball inside the
\ side walls. ball-max-y is paddle-top-px - 8: the ball's "death" line
\ sits exactly where it would first overlap the paddle, so handle-floor
\ fires the same frame the ball reaches paddle level without bouncing.
\ Painting never lands the ball on row 22, which keeps the paddle's
\ pixels safe from the ball's blit + cell-restore cycle.
8   constant ball-min-x
238 constant ball-max-x
8   constant ball-min-y
168 constant ball-max-y

: ball-reset         ( -- )
    ball-start-x ball-x !
    ball-start-y ball-y !
    ball-start-x ball-ox !
    ball-start-y ball-oy !
    ball-init-dx ball-dx !
    ball-init-dy ball-dy !
    0 ball-lost ! ;

\ Pixel-level erase using the all-zero pre-shifted sprite. Currently
\ unused — game.fs prefers cell-level restore so it can repaint bricks
\ underneath — but kept for symmetry with draw-ball.
: erase-ball         ( -- )
    blank-shifted ball-ox @ ball-oy @ blit8x ;

$47 constant ball-attr

: draw-ball          ( -- )
    ball-shifted ball-attr ball-x @ ball-y @ blit8xc ;

: ball-save-pos      ( -- )
    ball-x @ ball-ox !
    ball-y @ ball-oy ! ;

: advance-ball       ( -- )
    ball-dx @ ball-x +!
    ball-dy @ ball-y +! ;

: flip-dx            ( -- )    ball-dx @ negate ball-dx ! ;
: flip-dy            ( -- )    ball-dy @ negate ball-dy ! ;

\ Wall / ceiling bounces clamp position to the legal limit before flipping
\ direction. Without the clamp the ball could drift one frame deeper into
\ the wall before reversing, leaving a half-overlapped sprite.
: bounce-walls       ( -- )
    ball-x @ ball-min-x < if ball-min-x ball-x ! flip-dx exit then
    ball-x @ ball-max-x > if ball-max-x ball-x ! flip-dx then ;

: bounce-ceiling     ( -- )
    ball-y @ ball-min-y < if ball-min-y ball-y ! flip-dy then ;

: ball-below-paddle? ( -- flag )
    ball-y @ ball-max-y > ;

: handle-floor       ( -- )
    ball-below-paddle? if 1 ball-lost ! then ;

: ball-left-px       ( -- px )    ball-x @ ;
: ball-right-px      ( -- px )    ball-x @ 7 + ;
: ball-bottom-px     ( -- px )    ball-y @ 7 + ;

: ball-overlaps-paddle-x? ( -- flag )
    ball-right-px paddle-left-px  < if 0 exit then
    ball-left-px  paddle-right-px > if 0 exit then
    -1 ;

: ball-at-paddle-row?  ( -- flag )
    ball-bottom-px paddle-top-px < 0= ;

\ The 24-pixel-wide paddle is divided into six 4-pixel zones. The hit
\ offset (ball-centre minus paddle-left, in pixels) is mapped to a new
\ horizontal velocity: edges give the steepest deflection, the centre
\ gives the gentlest. There is no zero zone, so the ball always retains
\ some horizontal motion after a paddle hit.
\   offset    0..3   4..7   8..11  12..15  16..19  20..23
\   new dx    -3     -2     -1     +1      +2      +3
: zone-dx            ( hit-off -- dx )
    dup  4 < if drop -3 exit then
    dup  8 < if drop -2 exit then
    dup 12 < if drop -1 exit then
    dup 16 < if drop  1 exit then
    dup 20 < if drop  2 exit then
    drop  3 ;

: clamp-dx           ( dx -- dx )
    dup -3 < if drop -3 exit then
    dup  3 > if drop  3 exit then ;

\ paddle-bounce-dx adds the paddle's per-frame column delta to the zone
\ result, so a paddle moving into the contact pulls the bounce further
\ in that direction. The clamp keeps the ball from ever going faster
\ than 3 pixels per frame horizontally.
: paddle-bounce-dx   ( -- dx )
    ball-x @ 4 + paddle-left-px - zone-dx
    paddle-vel @ + clamp-dx ;

\ Order matters: snap y first (so the ball never visibly enters the
\ paddle row), then flip dy, then recompute dx. draw-paddle at the end
\ reasserts the paddle's pixels in case anything has touched them this
\ frame.
: bounce-paddle      ( -- )
    ball-at-paddle-row? 0= if exit then
    ball-overlaps-paddle-x? 0= if exit then
    paddle-top-px 8 - ball-y !
    flip-dy
    paddle-bounce-dx ball-dx !
    draw-paddle ;

: bounce-bricks      ( -- )
    ball-x @ ball-y @ ball-hits-brick? if
        flip-dy
        add-brick
    then ;

\ Ordering: advance position first, then resolve in priority order
\ walls -> ceiling -> bricks -> paddle -> floor. bounce-paddle is
\ checked after bricks so a brick directly above the paddle is hit
\ before paddle deflection, never both at once.
: ball-physics       ( -- )
    advance-ball
    bounce-walls
    bounce-ceiling
    bounce-bricks
    bounce-paddle
    handle-floor ;

: ball-paint         ( -- )
    draw-ball
    ball-save-pos ;

: ball-step          ( -- )
    ball-physics
    ball-paint ;
