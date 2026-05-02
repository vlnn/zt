\ stdlib/logic.fs — comparison and range-test helpers.
\
\ All comparisons follow the Forth convention: -1 (all bits set) for
\ true, 0 for false. `between?` is inclusive on both ends.

\ true if a is less than or equal to b
: <=          ( a b -- flag )    > 0= ;
\ true if a is greater than or equal to b
: >=          ( a b -- flag )    < 0= ;

\ true if a is less than or equal to b, unsigned
: u<=         ( a b -- flag )    swap u< 0= ;

\ true if n is in the inclusive range [lo, hi]
: between?    ( n lo hi -- flag )
    >r over <=  swap r> <=  and ;

\ clamp n to the inclusive range [lo, hi]
: clamp       ( n lo hi -- n' )  >r max r> min ;
