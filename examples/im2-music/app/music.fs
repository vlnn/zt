\ AY-3-8912 music driver, frame-locked to the IM 2 ULA interrupt.  Plays
\ an 8-note C-major arpeggio on channel A while the foreground thread
\ (rainbow border + random letters) keeps running uninterrupted.  Tone
\ periods are computed from the Spectrum 128's AY clock of 1.77345 MHz:
\ period N produces frequency clock / (16 * N).

require rand.fs
require ay.fs


\ The tune
\ ────────
\ Eight 16-bit periods spelling an octave-long C-major arpeggio.
\ tone-period masks the index into the [0, 7] range, so the ISR can
\ feed it a free-running counter and let the arpeggio cycle naturally.

create tone-table
    424 ,  377 ,  336 ,  317 ,  283 ,  252 ,  224 ,  212 ,

: tone-period   ( index -- period )
    7 and  2*  tone-table +  @ ;


\ Frame and step counters
\ ───────────────────────
\ border-tick drives the rainbow at 50 Hz (one increment per frame);
\ music-tick drives the arpeggio.  Sliding music-tick down by 3 bits
\ gives a step rate of 50 Hz / 8 ≈ 6 Hz — the perceived note speed.

variable border-tick
variable music-tick

: cycle-border    ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: advance-tick    ( -- )    1 music-tick +! ;
: note-index      ( -- i )  music-tick @ 3 rshift ;
: current-period  ( -- p )  note-index tone-period ;


\ The ISR
\ ───────
\ music-init is called once at startup to enable channel A's tone and
\ open its volume to max.  music-isr fires every 20 ms: it cycles the
\ border, advances the counter, and writes the period for whichever
\ note the counter currently selects.  Re-writing the period every
\ frame is harmless because the AY only resamples it on tone restart.

: music-init    ( -- )
    ay-mixer-tones-only ay-mixer!
    ay-volume-max       ay-vol-a! ;

: music-isr  ( -- )
    cycle-border
    advance-tick
    current-period ay-tone-a! ;


\ Foreground
\ ──────────
\ With the ISR installed, the foreground is free to do anything; here
\ it scribbles random uppercase letters and spaces at random positions,
\ same as the rainbow demo.  EI is required after im2-handler! because
\ the handler installer leaves interrupts disabled.

: random-letter   ( -- ch )
    27 random  dup 26 = if  drop 32  else  65 +  then ;

: random-position  ( -- col row )    32 random  24 random ;

: music  ( -- )
    ['] music-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
