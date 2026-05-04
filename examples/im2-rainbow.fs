\ Border-colour rainbow under IM 2, with the foreground thread spewing
\ random uppercase letters as fast as the CPU can manage.  The border
\ advances once per ULA frame interrupt; the random text streams in
\ between, proving the ISR runs concurrently with foreground Forth code.
\ This standalone version writes the ISR by hand in `:::` to show the
\ raw EI / RETI ceremony; the directory variant in im2-rainbow/ uses
\ the higher-level Forth `border` word from the stdlib.
\
\ Build:
\   uv run python -m zt.cli build examples/im2-rainbow.fs -o build/im2-rainbow.sna
\
\ Demonstrates the full IM 2 path: vector table allocation (auto-emitted
\ because IM2-HANDLER! appears in the live image), `IM2-HANDLER!` setting
\ up the JP slot, I, and IM 2, frame-rate ULA interrupts dispatched
\ through the table, the canonical `EI ; RETI` exit, and the main loop
\ running uninterrupted between fires.

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
