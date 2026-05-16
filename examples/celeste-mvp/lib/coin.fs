require core.fs
require sprites.fs
require player.fs


variable coin-collected
variable coins-count


variable coin-col
variable coin-row
variable coin-x
variable coin-y


create coin-tile
    $00 c, $3C c, $66 c, $7E c, $7E c, $66 c, $3C c, $00 c,


: coin-reset     ( -- )
    0 coin-collected !
    0 coins-count ! ;

: x-overlaps-coin?   ( -- flag )
    player-x @ 6 + coin-x @ < if 0 exit then
    coin-x @ 7 + player-x @ 1 + < if 0 exit then
    -1 ;

: y-overlaps-coin?   ( -- flag )
    player-y @ 7 + coin-y @ < if 0 exit then
    coin-y @ 7 + player-y @ < if 0 exit then
    -1 ;

: player-overlaps-coin?  ( -- flag )
    coin-collected @ if 0 exit then
    x-overlaps-coin? 0= if 0 exit then
    y-overlaps-coin? ;

: maybe-collect-coin  ( -- )
    player-overlaps-coin? 0= if exit then
    -1 coin-collected !
    1 coins-count +! ;

: paint-coin     ( -- )
    coin-collected @ if blank-tile coin-col @ coin-row @ blit8 exit then
    coin-tile coin-col @ coin-row @ blit8 ;
