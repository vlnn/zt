\ stdlib/rand.fs — 16-bit LCG random numbers.

variable rnd-seed

: rnd       ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
: seed!     ( n -- )         rnd-seed ! ;
: random    ( n -- 0..n-1 )  rnd swap u/mod drop ;
: between   ( lo hi -- n )   over - 1+ random + ;
: coin      ( -- flag )      rnd 1 and ;
: one-in    ( n -- flag )    random 0= ;
