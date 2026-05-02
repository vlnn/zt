\ stdlib/bit.fs — bit-packed boolean arrays.
\
\ Stores n bits in ceil(n/8) bytes; bit 0 is the least-significant bit
\ of the first byte. Indexes address bits across byte boundaries — bit
\ 8 is the LSB of the second byte, bit 15 is the MSB.
\
\ `allot` zeroes its bytes, so allocation is the standard pattern:
\
\   create flags  13 allot               \ 100 bits = ceil(100/8) bytes
\   17 flags bit-set
\   17 flags bit@                        \ -> 1
\   17 flags bit-flip                    \ now 0

require core.fs

\ number of bytes needed to hold n bits
: bit-bytes   ( n-bits -- n-bytes )    7 + 3 rshift ;

\ zero the first n bits of the array at addr
: bit-erase   ( n-bits addr -- )       swap bit-bytes 0 fill ;

\ byte offset within the array holding bit n
: bit-byte    ( n -- offset )          3 rshift ;
\ position (0..7) of bit n within its byte
: bit-pos     ( n -- pos )             7 and ;
\ single-byte mask for the bit at position p
: bit-mask    ( p -- mask )            1 swap lshift ;

\ resolve a bit index to the byte holding it and a single-byte mask
: bit-locate  ( n addr -- byte-addr mask )
    over bit-pos bit-mask >r
    swap bit-byte + r> ;

\ fetch bit n of the array at addr as 0 or 1
: bit@        ( n addr -- 0|1 )
    bit-locate swap c@ and  0= 0= 1 and ;

\ set bit n of the array at addr to 1
: bit-set     ( n addr -- )
    bit-locate  over c@ or  swap c! ;

\ reset bit n of the array at addr to 0
: bit-reset   ( n addr -- )
    bit-locate invert  over c@ and  swap c! ;

\ flip bit n of the array at addr
: bit-flip    ( n addr -- )
    bit-locate  over c@ xor  swap c! ;

\ store flag (any non-zero -> 1) to bit n of the array at addr
: bit!        ( flag n addr -- )
    rot if bit-set else bit-reset then ;
