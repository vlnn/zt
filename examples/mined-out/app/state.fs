\ Shared mutable state: score, current level, and the per-level lookup
\ tables that drive everything from screen colours through mine count
\ to which actors appear.

require core.fs


\ Score and level
\ ───────────────
\ score and level-no are the live counters.  ti is the within-level
\ tick timer, used by the map-blow and wind effects.
\ max-level-reached is the high-water mark feeding the level-select
\ menu; initial-bonus-pending is set by a level pick to deliver a
\ starting score on the first frame.

variable score
variable level-no
variable ti
variable max-level-reached
variable initial-bonus-pending


\ Per-level tables
\ ────────────────
\ Nine entries each, indexed by lx (level-no minus one).  Paper, border
\ and mine counts are bytes; the bonus is 16-bit because the upper
\ levels can reach 5000.

create level-paper    6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c, 6 c, 5 c,
create level-border   0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 2 c, 2 c,
create level-mines   50 c, 60 c, 70 c, 80 c, 90 c, 100 c, 20 c, 50 c, 82 c,
create level-bonus    0 , 250 , 750 , 1500 , 2200 , 2700 , 3500 , 4200 , 5000 ,

: lx             ( -- i )        level-no @ 1- ;

: level-paper@   ( -- p )        level-paper  lx + c@ ;
: level-border@  ( -- b )        level-border lx + c@ ;
: level-mines@   ( -- m )        level-mines  lx + c@ ;
: level-bonus@   ( -- n )        level-bonus  lx 2 * + @ ;


\ Level features
\ ──────────────
\ The original BASIC unlocks features at fixed level numbers; these
\ predicates centralise the boundaries so the rest of the code reads
\ as "if has-damsels?" instead of "if level >= 2 and level < 9".
\ has-bill? is exclusive — the final level is purely Bill — so all
\ other special features collapse to nothing on level 9.

: level>=?       ( n -- flag )   level-no @ swap < 0= ;
: has-bill?      ( -- flag )     9 level>=? ;
: pre-bill?      ( -- flag )     has-bill? 0= ;
: has-damsels?   ( -- flag )     2 level>=?  pre-bill?  and ;
: has-spreader?  ( -- flag )     3 level>=?  pre-bill?  and ;
: has-bug?       ( -- flag )     4 level>=? ;
: has-map-blow?  ( -- flag )     5 level>=?  pre-bill?  and ;
: has-closed-gap? ( -- flag )    level-no @ 8 = ;
: has-wind?       ( -- flag )    4 level>=?  pre-bill?  and ;


\ Level timer and triggers
\ ────────────────────────
\ ti increments once per frame in the playing state.  The map-blow
\ threshold scales with paper colour — lighter levels (higher paper)
\ blow later — and wind-period sets how often the wind nudges the
\ player along the trail.

: reset-ti            ( -- )        0 ti ! ;
: map-blow-threshold  ( -- n )      level-paper@ 260 * 70 + ;
: map-blow-due?       ( -- flag )
    has-map-blow? 0= if 0 exit then
    ti @ map-blow-threshold > ;

: wind-period         ( -- n )      level-paper@ 3 * 1+ ;


\ Level progression and colours
\ ─────────────────────────────
\ advance-level caps at 9 so the post-Bill state stays well-defined.
\ contrast-ink picks white ink on dark paper and black on light to
\ keep glyphs readable across the level palette.

: bump-max-level ( -- )
    level-no @ max-level-reached @ max  max-level-reached ! ;

: advance-level  ( -- )
    level-no @ 1+ 9 min level-no !
    bump-max-level ;

: contrast-ink   ( paper -- ink )   4 <  if 7 else 0 then ;

: apply-level-colors  ( -- )
    level-paper@ dup contrast-ink cls
    level-border@ border ;
