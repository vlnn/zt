\ stdlib/sprites.fs — helpers over the SP-stream blit primitives.
\
\ Wraps BLIT8 and BLIT8X with blank source data so erase operations don't
\ require each program to declare its own. Caller is responsible for
\ LOCK-SPRITES / UNLOCK-SPRITES around any blit (interrupts must be off
\ while the blit walks the source via SP).

require core.fs

\ 8-byte all-zero source for char-aligned erase via BLIT8
create blank8           8 allot

\ 128-byte all-zero source (8 shifts x 16 bytes) for pixel-aligned erase via BLIT8X
create blank-shifted  128 allot

\ erase the 8x8 char cell at (col, row)
: erase8     ( col row -- )    blank8         -rot blit8 ;

\ erase the 8x8 pixel-aligned area at (x, y)
: erase8x    ( x y -- )        blank-shifted  -rot blit8x ;
