require core.fs
require grid.fs
require sprites.fs


32 constant room-cols
24 constant room-rows
23 constant floor-row
22 constant step-row
26 constant step-left
30 constant step-right
 0 constant left-wall-col
31 constant right-wall-col
 1 constant solid
$07 constant room-attr


17 constant room-2-platform-row
12 constant room-2-platform-left
19 constant room-2-platform-right


create room-data  768 allot

variable current-room


: bind-room      ( -- )    room-data room-cols room-rows grid-set! ;

: fill-floor     ( -- )    solid floor-row fill-row ;
: fill-left-wall ( -- )    solid left-wall-col  fill-col ;
: fill-right-wall ( -- )   solid right-wall-col fill-col ;

: fill-step-cell ( col -- )   solid swap step-row grid! ;

: fill-step      ( -- )
    step-right 1+ step-left do
        i fill-step-cell
    loop ;

: fill-room-2-platform-cell  ( col -- )
    solid swap room-2-platform-row grid! ;

: fill-room-2-platform  ( -- )
    room-2-platform-right 1+ room-2-platform-left do
        i fill-room-2-platform-cell
    loop ;

: init-room-1    ( -- )
    bind-room
    0 grid-clear
    fill-floor
    fill-left-wall
    fill-right-wall
    fill-step ;

: init-room-2    ( -- )
    bind-room
    0 grid-clear
    fill-floor
    fill-left-wall
    fill-right-wall
    fill-room-2-platform ;

: init-room      ( -- )
    current-room @ 1 = if init-room-1 exit then
    current-room @ 2 = if init-room-2 exit then ;


: tile-sprite    ( v -- addr )
    if solid-tile else blank-tile then ;

: draw-cell      ( col row -- )
    2dup grid@ tile-sprite -rot blit8 ;

: draw-room      ( -- )
    room-rows 0 do
        room-cols 0 do
            i j draw-cell
        loop
    loop ;


: solid-at?      ( col row -- flag )    grid@ ;

: maybe-redraw-solid  ( col row -- )
    2dup solid-at? 0= if 2drop exit then
    solid-tile room-attr 2swap blit8c ;
