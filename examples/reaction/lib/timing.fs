20 constant ms-per-frame

\ convert a frame count to elapsed milliseconds
: frames>ms   ( frames -- ms )  ms-per-frame * ;
