\ Bitwise helpers used by the sierpinski demo.

\ true if every bit set in mask is clear in n
: bit-clear?  ( n mask -- flag )  and 0= ;
