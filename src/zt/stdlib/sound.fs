\ stdlib/sound.fs — BEEP-based sound effects.
\
\ Wraps the BEEP primitive (ROM BEEPER at $03B5).
\ Stack effect of BEEP: ( cycles period -- )
\   cycles: number of complete half-waves played (duration proxy)
\   period: loop count per half-wave (higher = lower pitch)

\ very short, sharp click — UI tap or step
: click        ( -- )            1 100 beep ;
\ short high-pitched chirp — selection or feedback cue
: chirp        ( -- )           20  40 beep ;
\ longer low tone — error or warning cue
: low-beep     ( -- )           50 400 beep ;
\ short high tone — confirmation cue
: high-beep    ( -- )           80  60 beep ;

\ play a fixed-duration tone at the given period (lower period = higher pitch)
: tone         ( period -- )    50 swap beep ;
