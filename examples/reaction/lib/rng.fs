\ Linear congruential RNG: seed' = seed * 25173 + 13849.  Standard
\ small-period parameters; mixes well enough for game randomness.
\ random reduces into a smaller range with mod, accepting the slight
\ bias for the cheaper code.

variable rnd-seed

: rnd      ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
: seed!    ( n -- )         rnd-seed ! ;
: random   ( n -- 0..n-1 )  rnd swap u/mod drop ;
