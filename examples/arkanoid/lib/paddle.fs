\ Paddle: 3-cell-wide, char-aligned, horizontal motion driven by O / P keys.
\
\ Position is stored as the leftmost char column (0..29), at fixed row 22.
\ Motion is throttled by paddle-rate: the paddle steps at most once every
\ paddle-rate frames so it isn't unplayable on a 50 Hz loop.

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

: paddle-can-step?   ( -- flag )
    paddle-tick @ 1+ paddle-tick !
    paddle-tick @ paddle-rate < if 0 exit then
    0 paddle-tick !
    -1 ;

: clamp-paddle       ( -- )
    paddle-col @ paddle-min-col < if paddle-min-col paddle-col ! exit then
    paddle-col @ paddle-max-col > if paddle-max-col paddle-col ! then ;

: move-left          ( -- )    -1 paddle-col +! clamp-paddle ;
: move-right         ( -- )     1 paddle-col +! clamp-paddle ;

: paddle-input       ( -- )
    paddle-can-step? 0= if exit then
    key-O key-state if move-left  exit then
    key-P key-state if move-right then ;

: paddle-left-px     ( -- px )    paddle-col @ 8 * ;
: paddle-right-px    ( -- px )    paddle-col @ paddle-w + 8 * 1- ;
: paddle-top-px      ( -- py )    paddle-row 8 * ;

: paddle-step        ( -- )
    erase-paddle
    paddle-input
    draw-paddle
    paddle-save-pos ;
