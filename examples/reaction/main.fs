require app/reaction.fs

\ entry point: seed RNG, zero stats, enter the round loop
: main  1 seed!  reset-stats  game-loop ;
