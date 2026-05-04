\ Two-voice AY song player driven by an IM 2 ISR.  The score is a flat
\ array of 16-bit period pairs (one per 16th note); the ISR walks it
\ one step every eight frames, sending each voice's period to its AY
\ channel.  A period of 0 means "rest" — the matching voice mutes.
\ The foreground (random letter spew) runs uninterrupted alongside.

require core.fs
require rand.fs
require ay.fs
require song-data.fs

variable border-tick
variable music-frame
variable song-step

4   constant /step
8   constant frames-per-step


\ AY voices
\ ─────────
\ music-init enables tone-only output on the mixer, then mutes channel
\ C since the song is two-voice.  play-or-mute-* writes a period and
\ unmutes the channel when the period is non-zero, or just mutes when
\ it's zero — the ISR doesn't have to branch on rest itself.

: music-init      ( -- )
    ay-mixer-tones-only ay-mixer!
    ay-volume-mute      ay-vol-c! ;

: play-or-mute-a  ( period -- )
    ?dup if  ay-tone-a!  ay-volume-max  ay-vol-a!
    else                 ay-volume-mute ay-vol-a!  then ;

: play-or-mute-b  ( period -- )
    ?dup if  ay-tone-b!  ay-volume-max  ay-vol-b!
    else                 ay-volume-mute ay-vol-b!  then ;


\ Score lookup
\ ────────────
\ Each step takes 4 bytes: a 16-bit period for voice A followed by one
\ for voice B.  step-addr does the offset arithmetic; step-period-a
\ and step-period-b extract the two halves.

: step-addr       ( step -- addr )  2* 2* song + ;
: step-period-a   ( step -- p )     step-addr     @ ;
: step-period-b   ( step -- p )     step-addr 2 + @ ;


\ Rhythm
\ ──────
\ The ISR fires every frame but only loads a new step every 8 frames.
\ music-frame is the within-step phase (0..7); song-step is the index
\ into the score and wraps at song-length so the piece loops.  The
\ ISR cycles the border on every frame regardless, so the rainbow
\ effect runs at the full 50 Hz.

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


\ Foreground
\ ──────────
\ Same shape as the rainbow demo's foreground: random letters at random
\ positions, forever, while the ISR plays the song.

: random-letter   ( -- ch )       26 random 65 + ;
: random-position ( -- col row )  32 random  24 random ;

: music           ( -- )
    music-init
    ['] music-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
