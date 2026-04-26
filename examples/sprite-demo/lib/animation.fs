\ Animation library for SP-stream sprites.
\
\ An "actor" is a 24-byte record:
\
\    +0   x        16-bit pixel x (signed for off-screen briefly)
\    +2   y        16-bit pixel y
\    +4   ox       previous x (used by actor-erase)
\    +6   oy       previous y
\    +8   frames   pointer to a table of pre-shifted sprite addresses
\   +10   count    number of frames in that table (1..255)
\   +11   frame    index of currently-displayed frame (0..count-1)
\   +12   tick     ticks remaining until next frame switch
\   +13   rate     ticks-per-frame (frame advances when tick reaches 0)
\   +14   state    8 bytes of trajectory-private scratch
\   +22   spare    2 bytes
\
\ The frame loop for one actor is:
\   actor-erase        \ blits BLANK at (ox, oy)
\   <trajectory>       \ updates (x, y) and any state
\   actor-tick         \ advances frame counter when its rate elapses
\   actor-draw         \ blits current frame at (x, y)
\   actor-save-pos     \ ox = x, oy = y (so next erase wipes the new spot)
\
\ Three trajectories are provided, each consuming an actor address:
\   linear-bounce      ( actor -- )  \ rectangular bounce off screen edges
\   sine-flier         ( actor -- )  \ horizontal scroll + vertical sine
\   gravity-bounce     ( actor -- )  \ gravity-driven parabola, bounce on floor
\
\ Each trajectory interprets `state` differently — see notes above each one.

require sprites-data.fs

\ -- Actor record layout -----------------------------------------------------

24 constant /actor

0  constant actor>x
2  constant actor>y
4  constant actor>ox
6  constant actor>oy
8  constant actor>frames
10 constant actor>count
11 constant actor>frame
12 constant actor>tick
13 constant actor>rate
14 constant actor>state

\ -- Field accessors ---------------------------------------------------------

: actor-x@   ( actor -- x )      actor>x +  @ ;
: actor-x!   ( x actor -- )      actor>x +  ! ;
: actor-y@   ( actor -- y )      actor>y +  @ ;
: actor-y!   ( y actor -- )      actor>y +  ! ;
: actor-ox@  ( actor -- ox )     actor>ox + @ ;
: actor-ox!  ( ox actor -- )     actor>ox + ! ;
: actor-oy@  ( actor -- oy )     actor>oy + @ ;
: actor-oy!  ( oy actor -- )     actor>oy + ! ;

\ State accessors. Each trajectory reads/writes its own slots.
: actor-s0@  ( actor -- w )      actor>state 0 + + @ ;
: actor-s0!  ( w actor -- )      actor>state 0 + + ! ;
: actor-s2@  ( actor -- w )      actor>state 2 + + @ ;
: actor-s2!  ( w actor -- )      actor>state 2 + + ! ;
: actor-s4@  ( actor -- w )      actor>state 4 + + @ ;
: actor-s4!  ( w actor -- )      actor>state 4 + + ! ;
: actor-s6@  ( actor -- w )      actor>state 6 + + @ ;
: actor-s6!  ( w actor -- )      actor>state 6 + + ! ;
: actor-s4c@ ( actor -- u8 )     actor>state 4 + + c@ ;
: actor-s4c! ( u8 actor -- )     actor>state 4 + + c! ;
: actor-s5c@ ( actor -- u8 )     actor>state 5 + + c@ ;
: actor-s5c! ( u8 actor -- )     actor>state 5 + + c! ;
: actor-s6c@ ( actor -- u8 )     actor>state 6 + + c@ ;
: actor-s6c! ( u8 actor -- )     actor>state 6 + + c! ;

\ -- Sine table (32 entries, signed bytes, range -20..+20) -------------------

create sine-table
    $00 c, $04 c, $08 c, $0B c, $0E c, $11 c, $12 c, $14 c,
    $14 c, $14 c, $12 c, $11 c, $0E c, $0B c, $08 c, $04 c,
    $00 c, $FC c, $F8 c, $F5 c, $F2 c, $EF c, $EE c, $EC c,
    $EC c, $EC c, $EE c, $EF c, $F2 c, $F5 c, $F8 c, $FC c,

\ Read sine-table[i] sign-extended to 16-bit.
: sine@  ( i -- s16 )
    sine-table + c@
    dup 128 < if exit then
    256 - ;

\ -- Erase / save-pos / draw / tick ------------------------------------------

: actor-erase  ( actor -- )
    \ Blit blank-shifted at (ox, oy). blit8x signature: ( shifted x y -- ).
    >r
    blank-shifted
    r@ actor-ox@
    r> actor-oy@
    blit8x ;

: actor-save-pos  ( actor -- )
    >r
    r@ actor-x@  r@ actor-ox!
    r@ actor-y@  r@ actor-oy!
    r> drop ;

\ Look up the address of the current frame: frames-table[frame-idx].
\ Each entry is a 2-byte cell.
: actor-current-frame  ( actor -- shifted-addr )
    dup actor>frame + c@   ( actor i )
    swap actor>frames + @  ( i table )
    swap 2* + @ ;

: actor-draw  ( actor -- )
    dup actor-current-frame   ( actor shifted )
    over actor-x@             ( actor shifted x )
    rot  actor-y@             ( shifted x y )
    blit8x ;

\ Decrement tick; when it reaches 0 advance frame index and reload tick = rate.
: actor-tick  ( actor -- )
    >r
    r@ actor>tick + c@ 1-     ( new-tick )
    dup 0= if
        drop
        r@ actor>frame + c@ 1+
        r@ actor>count + c@ mod
        r@ actor>frame + c!
        r@ actor>rate + c@
    then
    r@ actor>tick + c!
    r> drop ;

\ -- Helpers used by trajectories --------------------------------------------

\ Negate the word at addr in place.
: neg!  ( addr -- )  dup @ negate swap ! ;

\ Screen bounds for an 8x8 sprite drawn via BLIT8X.
\ X may go up to 240 (right column = 31, last valid). Y up to 184.
240 constant max-x
184 constant max-y

\ -- linear-bounce -----------------------------------------------------------
\ State: s0 = dx (s16), s2 = dy (s16).
\ Each step: x += dx, y += dy, bounce on edges.

: linear-bounce  ( actor -- )
    >r
    r@ actor-s0@  r@ actor>x + +!
    r@ actor-s2@  r@ actor>y + +!
    r@ actor-x@ 0< if
        0 r@ actor-x!
        r@ actor>state + neg!
    then
    r@ actor-x@ max-x > if
        max-x r@ actor-x!
        r@ actor>state + neg!
    then
    r@ actor-y@ 0< if
        0 r@ actor-y!
        r@ actor>state 2 + + neg!
    then
    r@ actor-y@ max-y > if
        max-y r@ actor-y!
        r@ actor>state 2 + + neg!
    then
    r> drop ;

\ -- sine-flier --------------------------------------------------------------
\ State: s0 = dx (s16), s2 = base-y (s16),
\        s4 = phase (u8), s5 = phase-step (u8).
\ x scrolls horizontally and wraps; y = base-y + sine-table[phase].

: sine-flier  ( actor -- )
    >r
    \ x += dx, then wrap to [0, max-x]
    r@ actor-s0@  r@ actor-x@ +
    dup 0< if drop max-x then
    dup max-x > if drop 0 then
    r@ actor-x!
    \ phase = (phase + step) and 31
    r@ actor-s4c@  r@ actor-s5c@ +  31 and  r@ actor-s4c!
    \ y = base-y + sine(phase)
    r@ actor-s4c@ sine@   r@ actor-s2@ +   r@ actor-y!
    r> drop ;

\ -- gravity-bounce ----------------------------------------------------------
\ State: s0 = dx (s16), s2 = dy (s16),
\        s4 = gravity (s16), s6 = floor-y (s16).
\ Each step: dy += gravity, x += dx, y += dy.
\ Floor hit (y > floor): clamp y, negate dy. Wall hit on x: negate dx.

: gravity-bounce  ( actor -- )
    >r
    \ dy += gravity
    r@ actor-s4@  r@ actor>state 2 + + +!
    \ x += dx
    r@ actor-s0@  r@ actor>x + +!
    \ y += dy
    r@ actor-s2@  r@ actor>y + +!
    \ wall bounces on x
    r@ actor-x@ 0< if
        0 r@ actor-x!
        r@ actor>state + neg!
    then
    r@ actor-x@ max-x > if
        max-x r@ actor-x!
        r@ actor>state + neg!
    then
    \ floor bounce on y
    r@ actor-y@  r@ actor-s6@  > if
        r@ actor-s6@  r@ actor-y!
        r@ actor>state 2 + + neg!
    then
    r> drop ;

\ -- player-control ----------------------------------------------------------
\ Keyboard-driven horizontal movement. State: s0 = speed (s16, pixels/tick).
\ O = move left, P = move right. Releases stop motion. y is left untouched
\ so callers can compose this with another vertical-motion trajectory if
\ they like, or just leave the actor at a fixed altitude.

79 constant key-O    \ ASCII 'O'
80 constant key-P    \ ASCII 'P'

: player-control  ( actor -- )
    >r
    key-O key-state if
        r@ actor-s0@ negate  r@ actor>x + +!
    then
    key-P key-state if
        r@ actor-s0@         r@ actor>x + +!
    then
    r@ actor-x@ 0< if
        0 r@ actor-x!
    then
    r@ actor-x@ max-x > if
        max-x r@ actor-x!
    then
    r> drop ;

\ -- High-level step helpers -------------------------------------------------
\ User typically writes:
\     : step-foo
\         my-actor dup actor-pre-step
\         dup my-trajectory
\         actor-post-step ;

: actor-pre-step   ( actor -- )  actor-erase ;
: actor-post-step  ( actor -- )
    dup actor-tick
    dup actor-draw
    actor-save-pos ;
