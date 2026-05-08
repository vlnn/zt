\ lib/pixel_addr.fs — Spectrum screen-byte address arithmetic.
\
\ Useful both as the back end of the Forth-level plot in plot.fs and
\ as a building block for clear-region helpers and tests.

\ Spectrum screen-byte address holding pixel (x,y).
\   addr = $4000 | ((y&$C0)<<5) | ((y&$07)<<8) | ((y&$38)<<2) | (x>>3)
:: pixel-byte  ( x y -- addr )
    dup 7 and    8 lshift                 \ (y & 7) << 8
    over 56 and  2 lshift  or             \ + (y & 56) << 2
    over 192 and 5 lshift  or             \ + (y & 192) << 5
    swap drop                             \ drop y
    swap 3 rshift  or                     \ + (x >> 3)
    16384 or ;                            \ + $4000

\ Bit mask for the pixel column inside its byte (high bit = leftmost).
:: pixel-mask  ( x -- mask )   7 and  7 swap -  1 swap lshift ;
