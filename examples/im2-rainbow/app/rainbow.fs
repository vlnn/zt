\ examples/im2-rainbow/app/rainbow.fs
\
\ The rainbow demo's app layer: the IM 2 handler that cycles the border, a
\ random-letter helper for the foreground spew, and the entry word `rainbow`
\ that wires them together. The handler runs once per ULA frame (50 Hz);
\ `rainbow` runs the main loop forever, emitting a random uppercase letter
\ between each fire.
\
\ Imports stdlib's rand.fs for the LCG-based `between` word.

require rand.fs

variable border-tick

: rainbow-isr  ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: random-letter  ( -- ch )
    27 random  dup 26 = if  drop 32  else  65 +  then ;

: random-position  ( -- col row )    32 random  24 random ;

: rainbow  ( -- )
    ['] rainbow-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
