\ Border-colour rainbow under IM 2, with the foreground thread spewing
\ random uppercase letters as fast as the CPU can manage.  The border
\ advances once per ULA frame interrupt; the random text streams in
\ between, proving the IM 2 ISR runs concurrently with foreground Forth
\ code.  Unlike the standalone im2-rainbow.fs, this version writes the
\ ISR as a regular `:` colon word over the stdlib `border` primitive.
\
\ Build:
\   uv run python -m zt.cli build examples/im2-rainbow/main.fs -o build/im2-rainbow.sna
\
\ Layout:
\   main.fs               entry; clears the screen and calls rainbow
\   app/rainbow.fs        ISR, random-letter, install + spew loop

require app/rainbow.fs

: main  0 7 cls  rainbow ;
