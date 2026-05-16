require core.fs
require sprites.fs
require room.fs


variable player-x
variable player-y
variable player-old-x
variable player-old-y
variable player-vx
variable player-vy
variable jumps-performed
variable wall-jumps-performed
variable z-prev
variable z-now
variable x-prev
variable x-now
variable coyote
variable jump-buffer
variable wall-jump-lockout
variable dash-state
variable dash-available
variable player-facing
variable dashes-performed


32 constant player-start-x
 8 constant player-start-y
 3 constant walk-spd-max
 1 constant walk-accel
 1 constant gravity
 3 constant max-fall-spd
-6 constant jump-vy
 6 constant coyote-max
 4 constant jump-buffer-max
 8 constant wall-jump-lockout-max
 6 constant dash-duration
 5 constant dash-spd
$43 constant player-attr
79 constant key-O
80 constant key-P
90 constant key-Z
88 constant key-X
81 constant key-Q
65 constant key-A
 4 constant dash-spd-diag


: player-xy      ( -- x y )    player-x @ player-y @ ;
: player-old-xy  ( -- x y )    player-old-x @ player-old-y @ ;

: respawn-player ( -- )
    player-start-x player-x !
    player-start-y player-y !
    0 player-vx !
    0 player-vy !
    0 z-prev !
    0 z-now !
    0 x-prev !
    0 x-now !
    0 coyote !
    0 jump-buffer !
    0 wall-jump-lockout !
    0 dash-state !
    1 dash-available !
    1 player-facing ! ;

: player-reset   ( -- )
    respawn-player
    player-start-x player-old-x !
    player-start-y player-old-y !
    0 jumps-performed !
    0 wall-jumps-performed !
    0 dashes-performed ! ;

: save-pos       ( -- )
    player-x @ player-old-x !
    player-y @ player-old-y ! ;


: draw-player    ( -- )    player-shifted player-attr player-xy blit8xc ;
: erase-player   ( -- )    blank-pixel player-old-xy blit8x ;


: px->cell       ( px -- cell )    2/ 2/ 2/ ;

: player-left-cell    ( -- col )    player-x @ 1 + px->cell ;
: player-right-cell   ( -- col )    player-x @ 6 + px->cell ;
: player-top-row      ( -- row )    player-y @ px->cell ;
: player-bottom-row   ( -- row )    player-y @ 7 + px->cell ;

: blit-left-col       ( -- col )    player-x @ px->cell ;
: blit-right-col      ( -- col )    player-x @ px->cell 1 + ;
: old-blit-left-col   ( -- col )    player-old-x @ px->cell ;
: old-blit-right-col  ( -- col )    player-old-x @ px->cell 1 + ;
: old-blit-top-row    ( -- row )    player-old-y @ px->cell ;
: old-blit-bottom-row ( -- row )    player-old-y @ 7 + px->cell ;

: redraw-room-around-player  ( -- )
    blit-left-col   player-top-row    maybe-redraw-solid
    blit-right-col  player-top-row    maybe-redraw-solid
    blit-left-col   player-bottom-row maybe-redraw-solid
    blit-right-col  player-bottom-row maybe-redraw-solid ;

: redraw-room-around-old  ( -- )
    old-blit-left-col   old-blit-top-row    maybe-redraw-solid
    old-blit-right-col  old-blit-top-row    maybe-redraw-solid
    old-blit-left-col   old-blit-bottom-row maybe-redraw-solid
    old-blit-right-col  old-blit-bottom-row maybe-redraw-solid ;


: aabb-overlaps-solid?  ( -- flag )
    player-left-cell  player-top-row    solid-at? if -1 exit then
    player-right-cell player-top-row    solid-at? if -1 exit then
    player-left-cell  player-bottom-row solid-at? if -1 exit then
    player-right-cell player-bottom-row solid-at? if -1 exit then
    0 ;


: step-left-1px   ( -- )
    -1 player-x +!
    aabb-overlaps-solid? if 1 player-x +! 0 player-vx ! then ;

: step-right-1px  ( -- )
    1 player-x +!
    aabb-overlaps-solid? if -1 player-x +! 0 player-vx ! then ;

: step-down-1px   ( -- )
    1 player-y +!
    aabb-overlaps-solid? if -1 player-y +! 0 player-vy ! then ;

: step-up-1px     ( -- )
    -1 player-y +!
    aabb-overlaps-solid? if 1 player-y +! 0 player-vy ! then ;


: clamp-fall-spd  ( vy -- vy' )
    dup max-fall-spd > if drop max-fall-spd then ;

: dashing?        ( -- flag )    dash-state @ 0 > ;

: apply-gravity   ( -- )
    dashing? if exit then
    player-vy @ gravity + clamp-fall-spd player-vy ! ;

: step-by-vy-1px  ( -- )
    player-vy @ dup 0= if drop exit then
    0 < if step-up-1px exit then
    step-down-1px ;

: apply-velocity  ( -- )
    player-vy @ dup 0= if drop exit then
    abs 0 do step-by-vy-1px loop ;

: step-by-vx-1px  ( -- )
    player-vx @ dup 0= if drop exit then
    0 < if step-left-1px exit then
    step-right-1px ;

: apply-velocity-x  ( -- )
    player-vx @ dup 0= if drop exit then
    abs 0 do step-by-vx-1px loop ;


: on-floor?      ( -- flag )
    1 player-y +!
    aabb-overlaps-solid?
    -1 player-y +! ;

: touching-left-wall?   ( -- flag )
    -1 player-x +!
    aabb-overlaps-solid?
    1 player-x +! ;

: touching-right-wall?  ( -- flag )
    1 player-x +!
    aabb-overlaps-solid?
    -1 player-x +! ;

: touching-wall?  ( -- flag )
    touching-left-wall? if -1 exit then
    touching-right-wall? ;


: o-held?        ( -- flag )    key-O key-state ;
: p-held?        ( -- flag )    key-P key-state ;
: z-held?        ( -- flag )    key-Z key-state ;
: q-held?        ( -- flag )    key-Q key-state ;
: a-held?        ( -- flag )    key-A key-state ;

: approach       ( cur target step -- new )
    >r over -
    dup abs r@ < if + r> drop exit then
    dup 0 < if drop r> - exit then
    drop r> + ;

: walk-target    ( -- target )
    o-held? if walk-spd-max negate exit then
    p-held? if walk-spd-max exit then
    0 ;

: update-vx      ( -- )
    dashing? if exit then
    wall-jump-lockout @ if exit then
    player-vx @ walk-target walk-accel approach player-vx ! ;

: poll-z         ( -- )    z-held? z-now ! ;
: z-just-pressed?   ( -- flag )    z-now @ z-prev @ 0= and ;
: save-z         ( -- )    z-now @ z-prev ! ;

: x-held?        ( -- flag )    key-X key-state ;
: poll-x         ( -- )    x-held? x-now ! ;
: x-just-pressed?   ( -- flag )    x-now @ x-prev @ 0= and ;
: save-x         ( -- )    x-now @ x-prev ! ;

: update-facing  ( -- )
    p-held? if  1 player-facing !  exit then
    o-held? if -1 player-facing !  exit then ;

: dash-dx-base   ( -- dx )
    p-held? if  1 exit then
    o-held? if -1 exit then
    0 ;

: dash-dy-base   ( -- dy )
    a-held? if  1 exit then
    q-held? if -1 exit then
    0 ;

: dash-dir-2d    ( -- dx dy )
    dash-dx-base dash-dy-base
    2dup or 0= if 2drop player-facing @ 0 then ;

: is-diagonal?   ( dx dy -- flag )
    0 <> swap 0 <> and ;

: dash-speed     ( dx dy -- dx dy spd )
    2dup is-diagonal? if dash-spd-diag else dash-spd then ;

: store-dash-velocity  ( dx dy spd -- )
    dup >r * player-vy !
    r> * player-vx ! ;

: dec-toward-zero  ( addr -- )
    dup @ 0= if drop exit then
    -1 swap +! ;

: tick-coyote    ( -- )
    on-floor? if coyote-max coyote ! exit then
    coyote dec-toward-zero ;

: tick-jump-buffer  ( -- )
    z-just-pressed? if jump-buffer-max jump-buffer ! exit then
    jump-buffer dec-toward-zero ;

: jump-armed?    ( -- flag )
    jump-buffer @ 0= if 0 exit then
    coyote @ 0= if 0 exit then
    -1 ;

: start-jump     ( -- )
    jump-vy player-vy !
    0 jump-buffer !
    0 coyote !
    1 jumps-performed +! ;

: start-wall-jump  ( -- )
    jump-vy player-vy !
    touching-left-wall? if walk-spd-max else walk-spd-max negate then
    player-vx !
    wall-jump-lockout-max wall-jump-lockout !
    0 jump-buffer !
    1 jumps-performed +!
    1 wall-jumps-performed +! ;

: tick-wall-jump-lockout  ( -- )
    wall-jump-lockout dec-toward-zero ;

: start-dash     ( -- )
    dash-dir-2d dash-speed store-dash-velocity
    dash-duration dash-state !
    0 dash-available !
    1 dashes-performed +! ;

: tick-dash      ( -- )
    dashing? if dash-state dec-toward-zero exit then
    on-floor? if 1 dash-available ! then ;

: maybe-start-dash  ( -- )
    dashing? if exit then
    dash-available @ 0= if exit then
    x-just-pressed? if start-dash then ;

: maybe-start-jump  ( -- )
    dashing? if exit then
    jump-armed? if start-jump exit then
    jump-buffer @ 0= if exit then
    on-floor? if exit then
    touching-wall? if start-wall-jump then ;

: rising?        ( -- flag )    player-vy @ 0 < ;

: maybe-cancel-jump  ( -- )
    dashing? if exit then
    z-now @ if exit then
    rising? 0= if exit then
    0 player-vy ! ;
