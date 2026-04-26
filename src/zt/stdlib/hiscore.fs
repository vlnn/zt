\ stdlib/hiscore.fs — three-initial high-score bookkeeping.
\
\ Usage:
\   hi-reset
\   score @ hi-beats? if
\       hi-name read-initials  score @ hi-set-score
\   then

require input.fs

variable hi-score

create hi-name
  65 c, 65 c, 65 c,            \ default initials AAA

\ true if n is strictly greater than the current high score
: hi-beats?      ( n -- flag )   hi-score @ > ;
\ store n as the new high score
: hi-set-score   ( n -- )        hi-score ! ;
\ store three character codes as the new high-score initials
: hi-set-name    ( c1 c2 c3 -- ) hi-name 2 + c!  hi-name 1+ c!  hi-name c! ;
\ reset score to zero and initials to AAA
: hi-reset       ( -- )
    0 hi-score !   65 65 65 hi-set-name ;

\ print the three-character high-score initials
: hi-type        ( -- )          hi-name 3 type ;

\ read three keypresses into the buffer at addr, echoing each as it is typed
: read-initials  ( addr -- )
    3 0 do
        wait-key dup emit
        over i + c!
    loop drop ;
