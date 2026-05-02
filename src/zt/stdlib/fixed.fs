\ stdlib/fixed.fs — 8.8 signed fixed-point arithmetic in a single cell.
\
\ Layout: high byte is integer (signed, -128..127), low byte is the
\ unsigned fractional part scaled by 1/256. So +1.0 = 256, +0.5 = 128,
\ -1.0 = -256.
\
\ Addition and subtraction work natively with `+` and `-` since both
\ operands share the same scale. Multiplication and division by an
\ integer also work natively with `*` and `/`. Multiplication of two
\ fixed values requires `f*` and is constrained to small magnitudes.
\
\ Usage:
\   3 >fixed             \ -> 768  (3.0)
\   768 fixed>int        \ -> 3
\   768 f.               \ prints "3.00 "
\   3 >fixed 2 *  f.     \ prints "6.00 "
\   3 >fixed 2 /  f.     \ prints "1.50 "

require core.fs

256 constant fixed-one
128 constant fixed-half

\ convert signed integer n to 8.8; |n| must be < 128
: >fixed       ( n -- f )            8 lshift ;

\ convert 8.8 to integer, truncating toward zero
: fixed>int    ( f -- n )
    dup 0< if  negate 8 rshift negate
         else  8 rshift                 then ;

\ multiply two 8.8 values; result valid when |result-real| < 128
: f*           ( f1 f2 -- f )
    2/ 2/ 2/ 2/  swap 2/ 2/ 2/ 2/  * ;

\ print n as zero-padded two-digit unsigned (n in 0..99), no trailing space
: pp.          ( pp -- )
    dup 10 < if 48 emit then (u.) ;

\ unsigned 0..99 fractional part of an unsigned 8.8 value
: u-frac       ( u-f -- pp )
    255 and 100 *  256 u/mod nip ;

\ print signed 8.8 as `[-]int.dd ` followed by a space
: f.           ( f -- )
    dup 0< if 45 emit  negate then
    dup 8 rshift (u.)
    46 emit
    u-frac pp.
    space ;
