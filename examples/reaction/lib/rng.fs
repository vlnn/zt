variable rnd-seed

: rnd      ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
: seed!    ( n -- )         rnd-seed ! ;
: random   ( n -- 0..n-1 )  rnd swap u/mod drop ;
