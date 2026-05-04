\ The rainbow demo's app layer: the IM 2 handler that cycles the border,
\ a random-letter helper for the foreground spew, and the entry word
\ `rainbow` that wires them together.  The handler runs once per ULA
\ frame (50 Hz); the foreground emits a random uppercase letter at a
\ random screen position between each fire, so the visible rate of
\ both effects is a function of how fast the CPU can run the loop.

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
