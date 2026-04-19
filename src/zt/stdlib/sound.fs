\ stdlib/sound.fs — BEEP-based sound effects.
\
\ Wraps the BEEP primitive (ROM BEEPER at $03B5).
\ Stack effect of BEEP: ( cycles period -- )
\   cycles: number of complete half-waves played (duration proxy)
\   period: loop count per half-wave (higher = lower pitch)

: click        ( -- )            1 100 beep ;
: chirp        ( -- )           20  40 beep ;
: low-beep     ( -- )           50 400 beep ;
: high-beep    ( -- )           80  60 beep ;

: tone         ( period -- )    50 swap beep ;
