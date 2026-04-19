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

: hi-beats?      ( n -- flag )   hi-score @ > ;
: hi-set-score   ( n -- )        hi-score ! ;
: hi-set-name    ( c1 c2 c3 -- ) hi-name 2 + c!  hi-name 1+ c!  hi-name c! ;
: hi-reset       ( -- )
    0 hi-score !   65 65 65 hi-set-name ;

: hi-type        ( -- )          hi-name 3 type ;

: read-initials  ( addr -- )
    3 0 do
        wait-key dup emit
        over i + c!
    loop drop ;
