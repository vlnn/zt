variable rnd-seed

\ advance the LCG and return the new 16-bit pseudo-random value
: rnd      ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
\ set the LCG seed
: seed!    ( n -- )         rnd-seed ! ;
\ return a pseudo-random value in the range 0..n-1
: random   ( n -- 0..n-1 )  rnd swap u/mod drop ;
