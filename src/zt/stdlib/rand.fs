\ stdlib/rand.fs — 16-bit LCG random numbers.

variable rnd-seed

\ advance the LCG and return the new 16-bit pseudo-random value
: rnd       ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
\ set the LCG seed
: seed!     ( n -- )         rnd-seed ! ;
\ return a pseudo-random value in the range 0..n-1
: random    ( n -- 0..n-1 )  rnd swap u/mod drop ;
\ return a pseudo-random value in the inclusive range lo..hi
: between   ( lo hi -- n )   over - 1+ random + ;
\ return a random one-bit flag (0 or 1) — coin flip
: coin      ( -- flag )      rnd 1 and ;
\ return true with probability 1/n
: one-in    ( n -- flag )    random 0= ;
