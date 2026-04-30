\ Ball physics for arkanoid.
\
\ State:
\   ball-x, ball-y    pixel position of the top-left of the 8x8 sprite
\   ball-ox, ball-oy  prior position (for erase via blit8x)
\   ball-dx, ball-dy  per-frame velocity (small signed integers)
\
\ Per-frame step:
\   1. erase at (ox, oy)
\   2. update (x, y) by (dx, dy), bouncing off walls and paddle, hitting bricks
\   3. draw at (x, y)
\   4. snapshot (x, y) into (ox, oy)

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

8   constant ball-min-x
238 constant ball-max-x
8   constant ball-min-y
176 constant ball-max-y

: ball-reset         ( -- )
    ball-start-x ball-x !
    ball-start-y ball-y !
    ball-start-x ball-ox !
    ball-start-y ball-oy !
    ball-init-dx ball-dx !
    ball-init-dy ball-dy !
    0 ball-lost ! ;

: erase-ball         ( -- )
    blank-shifted ball-ox @ ball-oy @ blit8x ;

: draw-ball          ( -- )
    ball-shifted ball-x @ ball-y @ blit8x ;

: ball-save-pos      ( -- )
    ball-x @ ball-ox !
    ball-y @ ball-oy ! ;

: advance-ball       ( -- )
    ball-dx @ ball-x +!
    ball-dy @ ball-y +! ;

: flip-dx            ( -- )    ball-dx @ negate ball-dx ! ;
: flip-dy            ( -- )    ball-dy @ negate ball-dy ! ;

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

: bounce-paddle      ( -- )
    ball-at-paddle-row? 0= if exit then
    ball-overlaps-paddle-x? 0= if exit then
    paddle-top-px 8 - ball-y !
    flip-dy ;

: bounce-bricks      ( -- )
    ball-x @ ball-y @ ball-hits-brick? if
        flip-dy
        add-brick
    then ;

: ball-step          ( -- )
    advance-ball
    bounce-walls
    bounce-ceiling
    bounce-bricks
    bounce-paddle
    handle-floor
    draw-ball
    ball-save-pos ;
