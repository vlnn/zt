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

: lx             ( -- i )        level-no @ 1- ;

: level-paper@   ( -- p )        level-paper  lx + c@ ;
: level-border@  ( -- b )        level-border lx + c@ ;
: level-mines@   ( -- m )        level-mines  lx + c@ ;
: level-bonus@   ( -- n )        level-bonus  lx 2 * + @ ;

: level>=?       ( n -- flag )   level-no @ swap < 0= ;
: has-bill?      ( -- flag )     9 level>=? ;
: has-damsels?   ( -- flag )     2 level>=?  has-bill? 0=  and ;
: has-spreader?  ( -- flag )     3 level>=?  has-bill? 0=  and ;
: has-bug?       ( -- flag )     4 level>=? ;
: has-map-blow?  ( -- flag )     5 level>=?  has-bill? 0=  and ;
: has-closed-gap? ( -- flag )    level-no @ 8 = ;
: has-wind?       ( -- flag )    4 level>=?  has-bill? 0=  and ;

: reset-ti            ( -- )        0 ti ! ;
: map-blow-threshold  ( -- n )      level-paper@ 260 * 70 + ;
: map-blow-due?       ( -- flag )
    has-map-blow? 0= if 0 exit then
    ti @ map-blow-threshold > ;

: wind-period         ( -- n )      level-paper@ 3 * 1+ ;

: bump-max-level ( -- )
    level-no @ max-level-reached @ max  max-level-reached ! ;

: advance-level  ( -- )
    level-no @ 1+ 9 min level-no !
    bump-max-level ;

: contrast-ink   ( paper -- ink )   4 <  if 7 else 0 then ;

: apply-level-colors  ( -- )
    level-paper@ dup contrast-ink cls
    level-border@ border ;
