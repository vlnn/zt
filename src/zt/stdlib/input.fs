\ stdlib/input.fs — higher-level input built on KEY, KEY?, KEY-STATE.
\
\ Usage:
\   54 55 56 57 set-keys!     \ ASCII 6 7 8 9 = L R U D
\   begin wait-frame  dir  step-by  again

variable key-left
variable key-right
variable key-up
variable key-down

\ bind the four direction keys (each as an ASCII code)
: set-keys!    ( left right up down -- )
    key-down !  key-up !  key-right !  key-left ! ;

\ 1 if the given keycode is currently held down, otherwise 0
: pressed?     ( keycode -- 0|1 )   key-state 1 and ;

\ 1 if the bound left key is held
: key-left?    ( -- 0|1 )   key-left  @ pressed? ;
\ 1 if the bound right key is held
: key-right?   ( -- 0|1 )   key-right @ pressed? ;
\ 1 if the bound up key is held
: key-up?      ( -- 0|1 )   key-up    @ pressed? ;
\ 1 if the bound down key is held
: key-down?    ( -- 0|1 )   key-down  @ pressed? ;

\ horizontal step from current input: -1, 0 or 1
: dx           ( -- dx )   key-right? key-left? - ;
\ vertical step from current input: -1, 0 or 1
: dy           ( -- dy )   key-down?  key-up?   - ;
\ combined direction vector from current input
: dir          ( -- dx dy )  dx dy ;

\ derive a direction vector from explicit left/right/up/down flags
: dir-from-flags  ( L R U D -- dx dy )
    swap - >r swap - r> ;

\ block until a key is pressed and return its code
: wait-key     ( -- c )   begin key? until key ;
\ discard any pending keypresses from the buffer
: drain-keys   ( -- )     begin key? 0= until ;
\ true if at least one key is pending
: any-key?     ( -- flag )  key? ;
