require rand.fs
require ay.fs
require song-data.fs

variable border-tick
variable music-frame
variable song-step

4   constant /step
8   constant frames-per-step

: music-init      ( -- )
    ay-mixer-tones-only ay-mixer!
    ay-volume-mute      ay-vol-c! ;

: ?dup            ( x -- 0 | x x )  dup if dup then ;

: play-or-mute-a  ( period -- )
    ?dup if  ay-tone-a!  ay-volume-max  ay-vol-a!
    else                 ay-volume-mute ay-vol-a!  then ;

: play-or-mute-b  ( period -- )
    ?dup if  ay-tone-b!  ay-volume-max  ay-vol-b!
    else                 ay-volume-mute ay-vol-b!  then ;

: step-addr       ( step -- addr )  2* 2* song + ;
: step-period-a   ( step -- p )     step-addr     @ ;
: step-period-b   ( step -- p )     step-addr 2 + @ ;

: cycle-border    ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: at-step-boundary?  ( -- f )       music-frame @ 0= ;

: bump-frame      ( -- )
    music-frame @ 1+  7 and  music-frame ! ;

: wrap-step       ( s -- s' )
    dup song-length = if drop 0 then ;

: bump-step       ( -- )
    song-step @ 1+ wrap-step  song-step ! ;

: load-current-step  ( -- )
    song-step @  dup step-period-a play-or-mute-a
                     step-period-b play-or-mute-b ;

: music-isr       ( -- )
    cycle-border
    at-step-boundary? if
        load-current-step
        bump-step
    then
    bump-frame ;

: random-letter   ( -- ch )       26 random 65 + ;
: random-position ( -- col row )  32 random  24 random ;

: music           ( -- )
    music-init
    ['] music-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
