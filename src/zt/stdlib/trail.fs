\ stdlib/trail.fs — fixed-size ring buffer of 16-bit cells.
\
\ Usage:
\   create t-buf  128 allot       \ = 64 cells * 2 bytes
\   t-buf 64 trail-init
\   5 3 pack-xy trail-push
\   0 trail@ unpack-xy  ( -- col row )

require core.fs

variable trail-buf
variable trail-cap
variable trail-head
variable trail-len

: trail-init   ( addr cap -- )
    trail-cap !  trail-buf !
    0 trail-head !  0 trail-len ! ;

: trail-reset  ( -- )  0 trail-head !  0 trail-len ! ;
: trail-len@   ( -- n )  trail-len @ ;

: trail-cell   ( idx -- addr )  2* trail-buf @ + ;

: advance-head   ( -- )
    trail-head @ 1+ trail-cap @ mod trail-head ! ;

: grow-len       ( -- )
    trail-len @ trail-cap @ < if 1 trail-len +! then ;

: trail-push   ( n -- )
    trail-head @ trail-cell !
    advance-head
    grow-len ;

: trail-physical  ( i -- p )
    trail-head @ + trail-len @ -
    trail-cap @ + trail-cap @ mod ;

: trail@       ( i -- n )   trail-physical trail-cell @ ;

: pack-xy     ( col row -- word )   swap 8 lshift or ;
: unpack-xy   ( word -- col row )   dup 255 and swap 8 rshift swap ;
