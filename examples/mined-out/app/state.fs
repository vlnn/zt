\ app/state.fs — shared mutable state: score, current level, level tables.

require core.fs

variable score
variable level-no
variable ti

create level-paper    6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c, 6 c,
create level-border   0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 2 c,
create level-mines   50 c, 60 c, 70 c, 80 c, 90 c, 100 c, 20 c, 50 c,
create level-bonus    0 , 250 , 750 , 1500 , 2200 , 2700 , 3500 , 4200 ,

: lx             ( -- i )        level-no @ 1- ;

: level-paper@   ( -- p )        level-paper  lx + c@ ;
: level-border@  ( -- b )        level-border lx + c@ ;
: level-mines@   ( -- m )        level-mines  lx + c@ ;
: level-bonus@   ( -- n )        level-bonus  lx 2 * + @ ;

: level>=?       ( n -- flag )   level-no @ swap < 0= ;
: has-damsels?   ( -- flag )     2 level>=? ;
: has-spreader?  ( -- flag )     3 level>=? ;
: has-bug?       ( -- flag )     4 level>=? ;
: has-map-blow?  ( -- flag )     5 level>=? ;
: has-bill?      ( -- flag )     9 level>=? ;

: reset-ti            ( -- )        0 ti ! ;
: map-blow-threshold  ( -- n )      level-paper@ 260 * 70 + ;
: map-blow-due?       ( -- flag )
    has-map-blow? 0= if 0 exit then
    ti @ map-blow-threshold > ;

: advance-level  ( -- )
    level-no @ 1+ 9 min level-no ! ;

: apply-level-colors  ( -- )
    level-paper@ 0 cls
    level-border@ border ;
