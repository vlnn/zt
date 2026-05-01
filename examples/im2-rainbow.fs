\ examples/im2-rainbow/main.fs
\
\ Border-colour rainbow under IM 2, with the main thread spewing random
\ letters as fast as the CPU can manage. The border colour advances once
\ per ULA frame interrupt; the random text streams in between, proving
\ the ISR runs concurrently with foreground Forth code.
\
\ Build:
\   uv run python -m zt.cli build examples/im2-rainbow/main.fs -o build/im2-rainbow.sna
\   (or just: make examples)
\
\ Run the resulting .sna in any Spectrum emulator. Expected behaviour:
\ the border cycles black -> blue -> red -> magenta -> green -> cyan -> yellow ->
\ white -> black at the 50 Hz frame rate, while the screen continuously
\ fills with random uppercase letters.
\
\ Demonstrates the full IM 2 path: vector table allocation (auto-emitted
\ because IM2-HANDLER! appears in the live image), `IM2-HANDLER!` setting up
\ the JP slot + I + IM 2, frame-rate ULA interrupts dispatched through the
\ table, the canonical `EI ; RETI` ceremony, and the main loop running
\ uninterrupted between fires.

require rand.fs

variable border-tick

::: rainbow-isr ( -- )
    push_af
    ' border-tick ld_a_ind_nn
    inc_a
    7 and_n
    $FE out_n_a
    ' border-tick ld_ind_nn_a
    pop_af
    ei
    reti ;

: random-letter  ( -- ch )    65 90 between ;

: main
    0 7 cls
    ['] rainbow-isr im2-handler!
    ei
    begin random-letter emit again ;
