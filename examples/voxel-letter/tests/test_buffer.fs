include test-lib.fs
require ../lib/buffer.fs

\ Buffer layout: 8 bytes, one per scanline.  rx, ry both in [0, 7]:
\   byte_offset = ry
\   bit_mask    = $80 >> rx

: clear-and-plot  ( rx ry -- )   clear-buffer  plot-buf ;

: test-origin-byte
    0 0 clear-and-plot
    letter-buf c@   $80 assert-eq ;

: test-x-7-lsb-bit
    7 0 clear-and-plot
    letter-buf c@   $01 assert-eq ;

: test-y-3-byte-3
    0 3 clear-and-plot
    letter-buf 3 + c@   $80 assert-eq
    letter-buf c@        0   assert-eq ;

: test-far-corner-last-byte-last-bit
    7 7 clear-and-plot
    letter-buf 7 + c@   $01 assert-eq ;

: test-plot-or-accumulates
    clear-buffer
    0 0 plot-buf
    1 0 plot-buf
    letter-buf c@   $C0 assert-eq ;

: test-plot-each-row-independent
    clear-buffer
    0 0 plot-buf            \ row 0
    7 1 plot-buf            \ row 1
    0 7 plot-buf            \ row 7
    letter-buf       c@  $80 assert-eq
    letter-buf 1 +   c@  $01 assert-eq
    letter-buf 7 +   c@  $80 assert-eq ;

: test-clear-zeros-everything
    8 0 do  $FF  letter-buf i +  c!  loop
    clear-buffer
    letter-buf c@        0 assert-eq
    letter-buf 4 + c@    0 assert-eq
    letter-buf 7 + c@    0 assert-eq ;
