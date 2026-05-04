\ Sound effects.  Today: short BEEP-based cues invoked synchronously
\ from game.fs.  Tomorrow: an IM 2 ISR drives an AY tracker on 128k
\ while these same audio-on-* words still fire one-shot SFX over the
\ top.  The hook seam is `audio-isr` — drop a real handler in here and
\ wire it with `['] audio-isr im2-handler! ei` from audio-init, and the
\ rest of the game keeps working unchanged.

require core.fs
require sound.fs
require ay.fs


\ Beeper effects
\ ──────────────
\ Tuned to be short enough not to stall the game loop perceptibly.
\ click is ~3ms; the rest run 4-12ms.

: sfx-move        ( -- )    1 200 beep ;
: sfx-rotate      ( -- )    2 100 beep ;
: sfx-lock        ( -- )    8 250 beep ;
: sfx-line-clear  ( -- )    chirp ;
: sfx-level-clear ( -- )    high-beep ;
: sfx-game-over   ( -- )    low-beep ;


\ IM 2 music seam
\ ───────────────
\ audio-isr is the entry point a future tracker will plug into.  Today
\ it's a no-op that just returns from interrupt; audio-init is also a
\ no-op so 48k builds stay quiet of AY writes.  When music lands:
\
\   ::: audio-isr
\       push_af push_bc push_de push_hl
\       \ ... advance pattern, write tone/volume regs ...
\       pop_hl pop_de pop_bc pop_af
\       ei reti ;
\
\   : audio-init
\       ay-mixer-tones-only ay-mixer!
\       ay-volume-max ay-vol-a!
\       ['] audio-isr im2-handler!
\       ei ;

: audio-init      ( -- ) ;


\ Public surface called from game events
\ ──────────────────────────────────────

: audio-on-move        ( -- )    sfx-move ;
: audio-on-rotate      ( -- )    sfx-rotate ;
: audio-on-lock        ( -- )    sfx-lock ;
: audio-on-line-clear  ( -- )    sfx-line-clear ;
: audio-on-level-clear ( -- )    sfx-level-clear ;
: audio-on-game-over   ( -- )    sfx-game-over ;
