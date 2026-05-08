\ lib/plot.fs — single-pixel set into Spectrum screen memory, in pure
\ Forth.  Reference implementation; about 10× slower than the :::-Z80
\ version in plot_native.fs.

require ../lib/pixel_addr.fs

\ set one pixel (OR-plot)
: plot         ( x y -- )
    over pixel-mask  >r
    pixel-byte  dup c@  r> or  swap c! ;
