\ examples/zlm-emit-test/main.fs — minimal 128K test of EMIT.
\
\ Same code path as zlm-tinychat for screen output, stripped to ~no other moving
\ parts. If this shows garbage in a real Spectrum 128 emulator while zlm-tinychat
\ also shows garbage, the bug is in zt's 128K SNA format (probably the $7FFD
\ port byte / ROM selection) rather than in any chatbot logic.

\ Force a bank into existence so the build is genuinely 128K-formatted.
0 in-bank create marker $00 c, end-bank

: main
    7 0 cls
    0 0 at-xy ." HI"
    0 1 at-xy ." Spectrum 128 EMIT works."
    begin again ;
