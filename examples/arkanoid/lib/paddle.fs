\ Paddle: 3-cell-wide, char-aligned, horizontal motion driven by O / P keys.
\
\ Position is stored as the leftmost char column (0..29), at fixed row 22.
\ Motion is throttled by paddle-rate: the paddle steps at most once every
\ paddle-rate frames so it isn't unplayable on a 50 Hz loop.
\
\ paddle-vel records the per-frame column delta (-1, 0, or +1). bounce-paddle
\ in ball.fs reads it to add some "english" to the ball when the player is
\ actively moving the paddle into the contact.

require core.fs
require sprites.fs

22 constant paddle-row
3  constant paddle-w
14 constant paddle-start-col
2  constant paddle-rate
1  constant paddle-min-col
28 constant paddle-max-col

variable paddle-col
variable paddle-old-col
variable paddle-tick
variable paddle-vel

79 constant key-O
80 constant key-P

: paddle-reset       ( -- )
    paddle-start-col paddle-col !
    paddle-start-col paddle-old-col !
    0 paddle-tick ! ;

: draw-paddle-at     ( col -- )
    >r
    paddle-left  r@        paddle-row blit8
    paddle-mid   r@ 1+     paddle-row blit8
    paddle-right r> 2 +    paddle-row blit8 ;

: erase-paddle-at    ( col -- )
    >r
    brick-blank  r@        paddle-row blit8
    brick-blank  r@ 1+     paddle-row blit8
    brick-blank  r> 2 +    paddle-row blit8 ;

: draw-paddle        ( -- )    paddle-col @ draw-paddle-at ;
: erase-paddle       ( -- )    paddle-old-col @ erase-paddle-at ;
: paddle-save-pos    ( -- )    paddle-col @ paddle-old-col ! ;

\ Throttle: only return -1 (true) every paddle-rate-th call. Each call
\ increments the tick; on overflow it resets and signals "step now". This
\ keeps the paddle from gliding 50 cells per second when O or P is held.
: paddle-can-step?   ( -- flag )
    paddle-tick @ 1+ paddle-tick !
    paddle-tick @ paddle-rate < if 0 exit then
    0 paddle-tick !
    -1 ;

\ Both clamp at the screen edge before mutating, not after, so we never
\ briefly write a column outside the legal range.
: move-left          ( -- )
    paddle-col @ paddle-min-col > if -1 paddle-col +! then ;
: move-right         ( -- )
    paddle-col @ paddle-max-col < if  1 paddle-col +! then ;

: paddle-input       ( -- )
    paddle-can-step? 0= if exit then
    key-O key-state if move-left  exit then
    key-P key-state if move-right then ;

: paddle-left-px     ( -- px )    paddle-col @ 8 * ;
: paddle-right-px    ( -- px )    paddle-col @ paddle-w + 8 * 1- ;
: paddle-top-px      ( -- py )    paddle-row 8 * ;

\ When the paddle moves one column, two of the three new cells overlap two
\ of the three old cells. Only the cell that was paddle and is no longer
\ paddle needs explicit blanking — the new draw-paddle will REPLACE-blit
\ the rest. paddle-trail-col returns that one trailing cell.
: paddle-trail-col   ( -- col )
    paddle-col @ paddle-old-col @ > if
        paddle-old-col @
    else
        paddle-old-col @ paddle-w + 1-
    then ;

: erase-paddle-trail ( -- )
    brick-blank paddle-trail-col paddle-row blit8 ;

: paddle-changed?    ( -- flag )
    paddle-col @ paddle-old-col @ <> ;

\ paddle-step is the one-frame entry point called by game-step. It always
\ resets paddle-vel first (so a stationary frame reads as zero velocity),
\ runs input, and only erases-and-redraws when the column actually changed.
: paddle-step        ( -- )
    0 paddle-vel !
    paddle-input
    paddle-changed? 0= if exit then
    paddle-col @ paddle-old-col @ - paddle-vel !
    erase-paddle-trail
    draw-paddle
    paddle-save-pos ;
