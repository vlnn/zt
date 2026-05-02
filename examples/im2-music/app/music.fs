\ examples/im2-music/app/music.fs
\
\ AY-3-8912 chip music driver, frame-locked to the IM 2 ULA interrupt.
\ Plays an 8-note C-major arpeggio on channel A while the foreground
\ thread (rainbow border + random letters) keeps running uninterrupted.
\
\ Tone periods are computed from the Spectrum 128's AY clock of
\ 1.77345 MHz: period N produces frequency clock / (16 * N).

require rand.fs
require ay.fs

create tone-table
    424 ,  377 ,  336 ,  317 ,  283 ,  252 ,  224 ,  212 ,

: tone-period   ( index -- period )
    7 and  2*  tone-table +  @ ;

variable border-tick
variable music-tick

: music-init    ( -- )
    ay-mixer-tones-only ay-mixer!
    ay-volume-max       ay-vol-a! ;

: cycle-border    ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: advance-tick    ( -- )    1 music-tick +! ;
: note-index      ( -- i )  music-tick @ 3 rshift ;
: current-period  ( -- p )  note-index tone-period ;

: music-isr  ( -- )
    cycle-border
    advance-tick
    current-period ay-tone-a! ;

: random-letter   ( -- ch )
    27 random  dup 26 = if  drop 32  else  65 +  then ;

: random-position  ( -- col row )    32 random  24 random ;

: music  ( -- )
    ['] music-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
