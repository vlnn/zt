\ examples/im2-rainbow/main.fs — entry point.
\
\ Border-colour rainbow under IM 2, with the foreground thread spewing
\ random uppercase letters as fast as the CPU can manage. The border colour
\ advances once per ULA frame interrupt; the random text streams in between,
\ proving the IM 2 ISR runs concurrently with foreground Forth code.
\
\ Build:
\   uv run python -m zt.cli build examples/im2-rainbow/main.fs -o build/im2-rainbow.sna
\   (or just: make examples)
\
\ Run the resulting .sna in any Spectrum emulator. Expected behaviour:
\ the border cycles black -> blue -> red -> magenta -> green -> cyan -> yellow ->
\ white -> black at the 50 Hz frame rate, while the screen continuously
\ fills with random uppercase letters (white on black).
\
\ Layout:
\   main.fs               - entry; clears the screen and calls rainbow
\   app/rainbow.fs        - ISR, random-letter, install + spew loop
\   tests/                - pytest acceptance + Forth unit tests
\
\ Demonstrates the full IM 2 path: vector table allocation (auto-emitted
\ because IM2-HANDLER! appears in the live image), `IM2-HANDLER!` setting
\ up the JP slot + I + IM 2, frame-rate ULA interrupts dispatched through
\ the table, the canonical `EI ; RETI` ceremony, and the foreground loop
\ running uninterrupted between fires.

require app/rainbow.fs

: main  0 7 cls  rainbow ;
