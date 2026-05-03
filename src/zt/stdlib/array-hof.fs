\ stdlib/array-hof.fs — higher-order functions over barray/carray/warray.
\
\ The xt is stashed in __hof-xt for the duration of one iteration. This is
\ NOT reentrant: calling another *-word inside the xt of an outer *-word
\ will clobber the saved xt. Don't nest, and don't call from an IM2 ISR
\ that itself uses these words.

require core.fs
require array.fs

variable __hof-xt

\ -- for-each: ( arr xt -- )  xt: ( v -- )

: for-each-word  ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do  dup i a-word@ __hof-xt @ execute  loop
    drop ;

: for-each-byte  ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do  dup i a-byte@ __hof-xt @ execute  loop
    drop ;

: for-each-bit   ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do  dup i a-bit@ __hof-xt @ execute  loop
    drop ;

\ -- map (in-place): ( arr xt -- )  xt: ( v -- v' )

: map-word  ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do
        dup i a-word@ __hof-xt @ execute
        over i a-word!
    loop
    drop ;

: map-byte  ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do
        dup i a-byte@ __hof-xt @ execute
        over i a-byte!
    loop
    drop ;

: map-bit   ( arr xt -- )
    __hof-xt !
    dup a-count dup 0= if 2drop exit then
    0 do
        dup i a-bit@ __hof-xt @ execute
        over i a-bit!
    loop
    drop ;

\ -- reduce: ( acc arr xt -- acc' )  xt: ( acc v -- acc' )

: reduce-word  ( acc arr xt -- acc' )
    __hof-xt !
    swap over a-count
    dup 0= if drop nip exit then
    0 do  over i a-word@ __hof-xt @ execute  loop
    nip ;

: reduce-byte  ( acc arr xt -- acc' )
    __hof-xt !
    swap over a-count
    dup 0= if drop nip exit then
    0 do  over i a-byte@ __hof-xt @ execute  loop
    nip ;

: reduce-bit   ( acc arr xt -- acc' )
    __hof-xt !
    swap over a-count
    dup 0= if drop nip exit then
    0 do  over i a-bit@ __hof-xt @ execute  loop
    nip ;

\ -- count-if: ( arr xt -- n )  xt: ( v -- flag )

: count-if-word  ( arr xt -- n )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 swap
    0 do
        over i a-word@ __hof-xt @ execute
        1 and +
    loop
    nip ;

: count-if-byte  ( arr xt -- n )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 swap
    0 do
        over i a-byte@ __hof-xt @ execute
        1 and +
    loop
    nip ;

: count-if-bit   ( arr xt -- n )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 swap
    0 do
        over i a-bit@ __hof-xt @ execute
        1 and +
    loop
    nip ;

\ -- any?: ( arr xt -- flag )  xt: ( v -- flag ) — early-terminating

: any?-word  ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 do
        dup i a-word@ __hof-xt @ execute
        if drop -1 unloop exit then
    loop
    drop 0 ;

: any?-byte  ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 do
        dup i a-byte@ __hof-xt @ execute
        if drop -1 unloop exit then
    loop
    drop 0 ;

: any?-bit   ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 exit then
    0 do
        dup i a-bit@ __hof-xt @ execute
        if drop -1 unloop exit then
    loop
    drop 0 ;

\ -- all?: ( arr xt -- flag )  vacuously true on empty

: all?-word  ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop -1 exit then
    0 do
        dup i a-word@ __hof-xt @ execute
        0= if drop 0 unloop exit then
    loop
    drop -1 ;

: all?-byte  ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop -1 exit then
    0 do
        dup i a-byte@ __hof-xt @ execute
        0= if drop 0 unloop exit then
    loop
    drop -1 ;

: all?-bit   ( arr xt -- flag )
    __hof-xt !
    dup a-count dup 0= if 2drop -1 exit then
    0 do
        dup i a-bit@ __hof-xt @ execute
        0= if drop 0 unloop exit then
    loop
    drop -1 ;

\ -- index-of?: ( arr xt -- i flag )  flag=-1 if found, 0 otherwise

: index-of?-word  ( arr xt -- i flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 0 exit then
    0 do
        dup i a-word@ __hof-xt @ execute
        if drop i -1 unloop exit then
    loop
    drop 0 0 ;

: index-of?-byte  ( arr xt -- i flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 0 exit then
    0 do
        dup i a-byte@ __hof-xt @ execute
        if drop i -1 unloop exit then
    loop
    drop 0 0 ;

: index-of?-bit   ( arr xt -- i flag )
    __hof-xt !
    dup a-count dup 0= if 2drop 0 0 exit then
    0 do
        dup i a-bit@ __hof-xt @ execute
        if drop i -1 unloop exit then
    loop
    drop 0 0 ;
