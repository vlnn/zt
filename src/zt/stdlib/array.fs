\ stdlib/array.fs — accessors for arrays defined by w: / c: / b: literals.
\ Layout: [count: 16-bit][data...]. Granularity is enforced at the access
\ word: a-word@/! treats data as cells, a-byte@/! as bytes, a-bit@/! as a
\ packed bit vector (LSB-first inside each byte).

: a-count  ( arr -- n )       @ ;
: a-data   ( arr -- addr )    2 + ;

: a-word@  ( arr i -- v )     2 *  swap a-data +  @ ;
: a-word!  ( v arr i -- )     2 *  swap a-data +  ! ;
: a-byte@  ( arr i -- b )     swap a-data +  c@ ;
: a-byte!  ( b arr i -- )     swap a-data +  c! ;

: a-bit@   ( arr i -- 0|1 )
    8 u/mod  rot a-data +  c@  swap rshift  1 and ;

: a-bit!   ( v arr i -- )
    8 u/mod  rot a-data +  >r
    1 swap lshift
    swap if   r@ c@ or
        else  invert r@ c@ and
        then
    r> c! ;
