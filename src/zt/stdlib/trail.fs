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

\ bind the ring buffer to addr with capacity cap cells, and clear it
: trail-init   ( addr cap -- )
    trail-cap !  trail-buf !
    0 trail-head !  0 trail-len ! ;

\ empty the trail without changing its buffer or capacity
: trail-reset  ( -- )  0 trail-head !  0 trail-len ! ;
\ current number of cells held in the trail
: trail-len@   ( -- n )  trail-len @ ;

\ address of the idx-th physical cell in the buffer
: trail-cell   ( idx -- addr )  2* trail-buf @ + ;

\ move the write head forward one slot, wrapping at capacity
: advance-head   ( -- )
    trail-head @ 1+ trail-cap @ mod trail-head ! ;

\ increment trail length up to capacity
: grow-len       ( -- )
    trail-len @ trail-cap @ < if 1 trail-len +! then ;

\ push n onto the trail, overwriting the oldest entry once full
: trail-push   ( n -- )
    trail-head @ trail-cell !
    advance-head
    grow-len ;

\ physical buffer index for the i-th oldest live cell
: trail-physical  ( i -- p )
    trail-head @ + trail-len @ -
    trail-cap @ + trail-cap @ mod ;

\ fetch the i-th oldest stored value (0 = oldest)
: trail@       ( i -- n )   trail-physical trail-cell @ ;

\ pack two byte-sized coordinates into a single 16-bit cell
: pack-xy     ( col row -- word )   swap 8 lshift or ;
\ unpack a 16-bit cell back into column and row bytes
: unpack-xy   ( word -- col row )   dup 255 and swap 8 rshift swap ;
