\ The sierpinski attribute grid lights a cell exactly when its column
\ and row share no bits — bit-clear? is the predicate that asks.

: bit-clear?  ( n mask -- flag )  and 0= ;
