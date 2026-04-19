require ../lib/math.fs
require ../lib/screen.fs
require ../lib/timing.fs

create wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,

variable phase

create phased 32 allot

: wave@       ( i -- n )        mod32 wave + c@ ;
: phased@     ( i -- n )        phased + c@ ;
: paper-attr  ( paper -- attr ) 3 lshift 64 or ;

: rephase  ( -- )
    scr-cols 0 do
        i phase @ + wave@
        phased i + c!
    loop ;

: draw-row  ( row -- )
    dup phased@
    swap row-addr
    scr-cols 0 do
        over i phased@ xor
        paper-attr
        over c!  1+
    loop
    2drop ;

: draw  ( -- )
    rephase
    scr-rows 0 do i draw-row loop ;

: plasma-init  ( -- )  0 phase !  draw ;

81 constant k-q
65 constant k-a
79 constant k-o
80 constant k-p
57 constant k-9
56 constant k-8
55 constant k-7
54 constant k-6

: up?     ( -- f )  k-q key-state  k-9 key-state  or ;
: down?   ( -- f )  k-a key-state  k-8 key-state  or ;
: left?   ( -- f )  k-o key-state  k-6 key-state  or ;
: right?  ( -- f )  k-p key-state  k-7 key-state  or ;

: dx      ( -- n )  right? left? - ;
: dy      ( -- n )  down?  up?   - ;

: react   ( -- )  dx dy scroll-attr ;

: animate ( -- )
    plasma-init
    begin wait-frame react again ;
