\ Sprite animation framework: the /actor record, accessors, a 32-entry
\ sine table, the erase/draw/tick lifecycle, three pluggable
\ trajectories (linear bounce, sine flier, gravity bounce), and a
\ keyboard player-control trajectory.  Callers compose actors by
\ choosing a trajectory and filling in trajectory-private `state`
\ bytes; the framework handles the rest.

require sprites-data.fs
require array.fs


\ The /actor record
\ ─────────────────
\ 24 bytes per actor:
\
\   +0   x        16-bit pixel x (signed for off-screen briefly)
\   +2   y        16-bit pixel y
\   +4   ox       previous x (used by actor-erase)
\   +6   oy       previous y
\   +8   frames   pointer to a table of pre-shifted sprite addresses
\  +10   count    number of frames in the table
\  +11   frame    index of the currently-displayed frame
\  +12   tick     ticks remaining until the next frame switch
\  +13   rate     ticks-per-frame
\  +14   state    8 bytes of trajectory-private scratch
\  +22   spare    2 unused bytes
\
\ Per-frame lifecycle for one actor: erase at (ox, oy), call its
\ trajectory to update (x, y), advance the frame counter when its
\ rate elapses, draw the new frame, save (x, y) into (ox, oy).

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


\ Field accessors
\ ───────────────
\ Position fields get full @/! pairs.  The state slots are addressed
\ by their byte offset within state; trajectories pick whichever slot
\ width they need (cell or byte) without any pre-declared layout.

: actor-x@   ( actor -- x )      actor>x +  @ ;
: actor-x!   ( x actor -- )      actor>x +  ! ;
: actor-y@   ( actor -- y )      actor>y +  @ ;
: actor-y!   ( y actor -- )      actor>y +  ! ;
: actor-ox@  ( actor -- ox )     actor>ox + @ ;
: actor-ox!  ( ox actor -- )     actor>ox + ! ;
: actor-oy@  ( actor -- oy )     actor>oy + @ ;
: actor-oy!  ( oy actor -- )     actor>oy + ! ;

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


\ The sine table
\ ──────────────
\ 32 signed bytes covering one full period, range -20..+20.  Stored as
\ unsigned bytes; sine@ sign-extends the result to a 16-bit value so
\ trajectories can add it directly to a y coordinate.

c: sine-table
    $00 c, $04 c, $08 c, $0B c, $0E c, $11 c, $12 c, $14 c,
    $14 c, $14 c, $12 c, $11 c, $0E c, $0B c, $08 c, $04 c,
    $00 c, $FC c, $F8 c, $F5 c, $F2 c, $EF c, $EE c, $EC c,
    $EC c, $EC c, $EE c, $EF c, $F2 c, $F5 c, $F8 c, $FC c,
;

: sine@  ( i -- s16 )
    sine-table swap a-byte@
    dup 128 < if exit then
    256 - ;


\ The erase/draw lifecycle
\ ────────────────────────
\ actor-erase blits the all-zero blank-shifted sprite at (ox, oy),
\ wiping wherever the actor was last frame.  actor-draw looks up the
\ current frame in the actor's frames table and blits it at (x, y).
\ actor-save-pos copies (x, y) into (ox, oy) so the next erase wipes
\ the new spot.  actor-tick decrements the per-frame counter and, when
\ it reaches zero, advances the frame index modulo count and reloads
\ tick = rate.

: actor-erase  ( actor -- )
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

: actor-current-frame  ( actor -- shifted-addr )
    dup actor>frame + c@
    swap actor>frames + @
    swap a-word@ ;

: actor-draw  ( actor -- )
    dup actor-current-frame
    over actor-x@
    rot  actor-y@
    blit8x ;

: actor-tick  ( actor -- )
    >r
    r@ actor>tick + c@ 1-
    dup 0= if
        drop
        r@ actor>frame + c@ 1+
        r@ actor>count + c@ mod
        r@ actor>frame + c!
        r@ actor>rate + c@
    then
    r@ actor>tick + c!
    r> drop ;


\ Bounds and small helpers
\ ────────────────────────
\ An 8x8 sprite drawn via blit8x can sit at x in [0, 240] and y in
\ [0, 184] before clipping the right or bottom edges.  neg! flips the
\ sign of a cell in place — used by the bouncing trajectories to flip
\ velocity on contact with an edge.

: neg!  ( addr -- )  dup @ negate swap ! ;

240 constant max-x
184 constant max-y


\ linear-bounce
\ ─────────────
\ State: s0 = dx, s2 = dy.  Each tick adds the velocity to position;
\ when an edge is hit, position clamps to that edge and the matching
\ velocity is negated so the next tick moves away.

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


\ sine-flier
\ ──────────
\ State: s0 = dx, s2 = base-y, s4 = phase byte, s5 = phase step.
\ x scrolls horizontally and wraps at the screen edges; y is base-y
\ plus sine-table[phase], with phase advancing by step every tick and
\ wrapping into [0, 31].  dx stays positive — there's no bouncing,
\ just an endless rightward (or leftward) scroll.

: sine-flier  ( actor -- )
    >r
    r@ actor-s0@  r@ actor-x@ +
    dup 0< if drop max-x then
    dup max-x > if drop 0 then
    r@ actor-x!
    r@ actor-s4c@  r@ actor-s5c@ +  31 and  r@ actor-s4c!
    r@ actor-s4c@ sine@   r@ actor-s2@ +   r@ actor-y!
    r> drop ;


\ gravity-bounce
\ ──────────────
\ State: s0 = dx, s2 = dy, s4 = gravity, s6 = floor-y.  Each tick adds
\ gravity to dy, then dx and dy to position.  Hitting a wall negates
\ dx; hitting the floor clamps y and negates dy, so the bounce loses
\ no energy (and the ball will keep bouncing forever — by design, for
\ a demo).

: gravity-bounce  ( actor -- )
    >r
    r@ actor-s4@  r@ actor>state 2 + + +!
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
    r@ actor-y@  r@ actor-s6@  > if
        r@ actor-s6@  r@ actor-y!
        r@ actor>state 2 + + neg!
    then
    r> drop ;


\ player-control
\ ──────────────
\ Keyboard-driven horizontal movement.  State: s0 = speed.  O moves
\ left, P moves right; releases stop motion.  y is left untouched so
\ callers can compose this with another vertical-motion trajectory or
\ leave the actor at a fixed altitude.

79 constant key-O
80 constant key-P

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


\ Step helpers
\ ────────────
\ The boilerplate around every trajectory is the same: erase before,
\ tick + draw + save-pos after.  These two helpers wrap the pre/post
\ pieces so a step word reduces to "erase, run trajectory, post-step".

: actor-pre-step   ( actor -- )  actor-erase ;
: actor-post-step  ( actor -- )
    dup actor-tick
    dup actor-draw
    actor-save-pos ;
