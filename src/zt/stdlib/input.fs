\ stdlib/input.fs — higher-level input built on KEY, KEY?, KEY-STATE.
\
\ Usage:
\   54 55 56 57 set-keys!     \ ASCII 6 7 8 9 = L R U D
\   begin wait-frame  dir  step-by  again

variable key-left
variable key-right
variable key-up
variable key-down

: set-keys!    ( left right up down -- )
    key-down !  key-up !  key-right !  key-left ! ;

: pressed?     ( keycode -- 0|1 )   key-state 1 and ;

: key-left?    ( -- 0|1 )   key-left  @ pressed? ;
: key-right?   ( -- 0|1 )   key-right @ pressed? ;
: key-up?      ( -- 0|1 )   key-up    @ pressed? ;
: key-down?    ( -- 0|1 )   key-down  @ pressed? ;

: dx           ( -- dx )   key-right? key-left? - ;
: dy           ( -- dy )   key-down?  key-up?   - ;
: dir          ( -- dx dy )  dx dy ;

: dir-from-flags  ( L R U D -- dx dy )
    swap - >r swap - r> ;

: wait-key     ( -- c )   begin key? until key ;
: drain-keys   ( -- )     begin key? 0= until ;
: any-key?     ( -- flag )  key? ;
