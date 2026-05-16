require core.fs
require sprites.fs
require player.fs


variable deaths


variable spikes-col
variable spikes-row
variable spikes-x
variable spikes-y


create spike-tile
    $18 c, $3C c, $66 c, $66 c, $FF c, $FF c, $7E c, $3C c,


: spikes-reset   ( -- )
    0 deaths ! ;

: x-overlaps-spikes?  ( -- flag )
    player-x @ 6 + spikes-x @ < if 0 exit then
    spikes-x @ 23 + player-x @ 1 + < if 0 exit then
    -1 ;

: y-overlaps-spikes?  ( -- flag )
    player-y @ 7 + spikes-y @ < if 0 exit then
    spikes-y @ 7 + player-y @ < if 0 exit then
    -1 ;

: player-overlaps-spikes?  ( -- flag )
    x-overlaps-spikes? 0= if 0 exit then
    y-overlaps-spikes? ;

: maybe-kill-player  ( -- )
    player-overlaps-spikes? 0= if exit then
    respawn-player
    1 deaths +! ;

: paint-spikes   ( -- )
    spike-tile spikes-col @      spikes-row @ blit8
    spike-tile spikes-col @ 1 +  spikes-row @ blit8
    spike-tile spikes-col @ 2 +  spikes-row @ blit8 ;
