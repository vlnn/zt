require rand.fs
require song-data.fs

variable border-tick
variable music-frame
variable song-step

$38 constant ay-mixer-tones-only
$0F constant ay-volume-max
0   constant ay-volume-mute
4   constant /step
8   constant frames-per-step

::: ay-set  ( val reg -- )
    pop_de
    $FFFD ld_bc_nn  ld_a_l  out_c_a
    $BFFD ld_bc_nn  ld_a_e  out_c_a
    pop_hl ;

: enable-tones    ( -- )    ay-mixer-tones-only 7 ay-set ;
: silence-c       ( -- )    ay-volume-mute 10 ay-set ;
: music-init      ( -- )    enable-tones silence-c ;

: low-byte        ( n -- lo )  255 and ;
: high-byte       ( n -- hi )  8 rshift ;

: tone-a!         ( period -- )
    dup low-byte  0 ay-set
        high-byte 1 ay-set ;

: tone-b!         ( period -- )
    dup low-byte  2 ay-set
        high-byte 3 ay-set ;

: vol-a!          ( vol -- )  8 ay-set ;
: vol-b!          ( vol -- )  9 ay-set ;

: ?dup            ( x -- 0 | x x )  dup if dup then ;

: play-or-mute-a  ( period -- )
    ?dup if  tone-a!  ay-volume-max vol-a!
    else            ay-volume-mute vol-a!  then ;

: play-or-mute-b  ( period -- )
    ?dup if  tone-b!  ay-volume-max vol-b!
    else            ay-volume-mute vol-b!  then ;

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
