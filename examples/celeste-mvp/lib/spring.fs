require core.fs
require sprites.fs
require player.fs


variable spring-bounces


variable spring-col
variable spring-row
variable spring-x
variable spring-y
-12 constant spring-vy


create spring-tile
    $00 c, $24 c, $3C c, $24 c, $3C c, $24 c, $7E c, $FF c,


: spring-reset       ( -- )
    0 spring-bounces ! ;

: x-overlaps-spring?  ( -- flag )
    player-x @ 6 + spring-x @ < if 0 exit then
    spring-x @ 7 + player-x @ 1 + < if 0 exit then
    -1 ;

: y-overlaps-spring?  ( -- flag )
    player-y @ 7 + spring-y @ < if 0 exit then
    spring-y @ 7 + player-y @ < if 0 exit then
    -1 ;

: player-overlaps-spring?  ( -- flag )
    x-overlaps-spring? 0= if 0 exit then
    y-overlaps-spring? ;

: descending?    ( -- flag )    player-vy @ 0 > ;

: maybe-bounce-on-spring  ( -- )
    player-overlaps-spring? 0= if exit then
    descending? 0= if exit then
    spring-vy player-vy !
    1 dash-available !
    1 spring-bounces +! ;

: paint-spring       ( -- )
    spring-tile spring-col @ spring-row @ blit8 ;
