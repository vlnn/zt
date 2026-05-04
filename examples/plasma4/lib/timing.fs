\ Frame timing.  20 ms per frame at the Spectrum's 50 Hz interrupt;
\ the helper turns frame counts into milliseconds.

20 constant ms-per-frame

: frames>ms   ( frames -- ms )  ms-per-frame * ;
