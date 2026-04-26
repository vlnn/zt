\ app/state.fs — shared mutable state: score, current level, level tables.

require core.fs

variable score
variable level-no
variable ti
variable max-level-reached
variable initial-bonus-pending

create level-paper    6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c, 6 c, 5 c,
create level-border   0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 2 c, 2 c,
create level-mines   50 c, 60 c, 70 c, 80 c, 90 c, 100 c, 20 c, 50 c, 82 c,
create level-bonus    0 , 250 , 750 , 1500 , 2200 , 2700 , 3500 , 4200 , 5000 ,

\ zero-based index into the level-* tables for the current level
: lx             ( -- i )        level-no @ 1- ;

\ paper colour for the current level
: level-paper@   ( -- p )        level-paper  lx + c@ ;
\ border colour for the current level
: level-border@  ( -- b )        level-border lx + c@ ;
\ mine count for the current level
: level-mines@   ( -- m )        level-mines  lx + c@ ;
\ starting bonus (cells, 16-bit) for the current level
: level-bonus@   ( -- n )        level-bonus  lx 2 * + @ ;

\ true if the current level number is at least n
: level>=?       ( n -- flag )   level-no @ swap < 0= ;
\ true on the final, Bill-rescue level
: has-bill?      ( -- flag )     9 level>=? ;
\ true on every level before Bill's
: pre-bill?      ( -- flag )     has-bill? 0= ;
\ true if damsels appear on the current level
: has-damsels?   ( -- flag )     2 level>=?  pre-bill?  and ;
\ true if the mine-spreader appears on the current level
: has-spreader?  ( -- flag )     3 level>=?  pre-bill?  and ;
\ true if the bug appears on the current level
: has-bug?       ( -- flag )     4 level>=? ;
\ true if the periodic "map blow" effect happens on this level
: has-map-blow?  ( -- flag )     5 level>=?  pre-bill?  and ;
\ true on the level whose top gap is closed
: has-closed-gap? ( -- flag )    level-no @ 8 = ;
\ true if wind drifts the player on the current level
: has-wind?       ( -- flag )    4 level>=?  pre-bill?  and ;

\ zero the level timer
: reset-ti            ( -- )        0 ti ! ;
\ ti value at which the next map-blow event triggers
: map-blow-threshold  ( -- n )      level-paper@ 260 * 70 + ;
\ true when the level timer has reached the map-blow threshold
: map-blow-due?       ( -- flag )
    has-map-blow? 0= if 0 exit then
    ti @ map-blow-threshold > ;

\ tick count between successive wind nudges on the current level
: wind-period         ( -- n )      level-paper@ 3 * 1+ ;

\ update the highest level the player has reached so far
: bump-max-level ( -- )
    level-no @ max-level-reached @ max  max-level-reached ! ;

\ move on to the next level (capped at 9), and remember the new high water mark
: advance-level  ( -- )
    level-no @ 1+ 9 min level-no !
    bump-max-level ;

\ pick a contrasting ink colour for the given paper
: contrast-ink   ( paper -- ink )   4 <  if 7 else 0 then ;

\ apply the current level's paper, ink and border to the screen
: apply-level-colors  ( -- )
    level-paper@ dup contrast-ink cls
    level-border@ border ;
