require ./lib/math.fs
require ./lib/screen.fs

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
    dup phased@                         ( row row_wave )
    swap row-addr                       ( row_wave addr )
    scr-cols 0 do
        over i phased@ xor              ( row_wave addr paper )
        paper-attr                      ( row_wave addr attr )
        over c!  1+                     ( row_wave addr' )
    loop
    2drop ;

: draw  ( -- )
    rephase
    scr-rows 0 do i draw-row loop ;

: step     ( -- )   1 phase +! ;
: animate           begin draw step again ;

: main animate ;
