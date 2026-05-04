\ Paddle: 3-cell-wide, char-aligned, horizontal motion driven by O / P
\ keys.  Position is stored as the leftmost char column, fixed at row
\ 22.  Motion is throttled so the paddle isn't unplayable on a 50 Hz
\ loop; paddle-vel records the per-frame column delta so ball.fs can
\ add english to the bounce when the player is actively moving into
\ the contact.

require core.fs
require sprites.fs


\ State
\ ─────
\ paddle-col is the live column; paddle-old-col is the previous frame's
\ column (used for trail erase).  paddle-tick counts up between motion
\ steps; paddle-vel is the per-frame -1/0/+1 delta exposed to ball.fs.

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


\ Drawing
\ ───────
\ Three blits per paddle: left cap, middle, right cap.  draw-paddle-at
\ takes an explicit column so paddle-step can also use it for the
\ erase phase via brick-blank.

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


\ Throttling and motion
\ ─────────────────────
\ paddle-can-step? returns true once every paddle-rate calls — the
\ rest tick the counter and signal "wait".  Both clamping moves test
\ against the screen edge before mutating, so the column never briefly
\ holds an out-of-range value.

: paddle-can-step?   ( -- flag )
    paddle-tick @ 1+ paddle-tick !
    paddle-tick @ paddle-rate < if 0 exit then
    0 paddle-tick !
    -1 ;

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


\ Per-frame integration
\ ─────────────────────
\ When the paddle moves one column, two of three new cells overlap two
\ of three old cells; only the cell that was paddle and is no longer
\ paddle needs explicit blanking, since the new draw will overwrite
\ the rest.  paddle-trail-col is that one trailing cell.  paddle-step
\ is the entry point: zero the velocity so a stationary frame reads
\ zero, run input, and only erase-redraw when the column changed.

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

: paddle-step        ( -- )
    0 paddle-vel !
    paddle-input
    paddle-changed? 0= if exit then
    paddle-col @ paddle-old-col @ - paddle-vel !
    erase-paddle-trail
    draw-paddle
    paddle-save-pos ;
