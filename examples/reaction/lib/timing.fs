\ Frame timing.  The Spectrum's interrupt fires at 50 Hz, so each frame
\ is 20 ms — frames>ms turns frame counts into wall-clock milliseconds.

20 constant ms-per-frame

: frames>ms   ( frames -- ms )  ms-per-frame * ;
