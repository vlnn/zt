\ AY music driven by an IM 2 ISR, with the rainbow-demo foreground
\ (border colour cycle plus random-letter spew) running on top.  The
\ ISR writes channel A's 16-bit tone period from a small table once per
\ ULA frame; the foreground proves the music plays concurrently with
\ ordinary Forth code.
\
\ Build (must be 128k — AY is 128k-only):
\   uv run python -m zt.cli build examples/im2-music/main.fs \
\       -o build/im2-music.sna --target 128k
\
\ Expected behaviour: an 8-note C-major arpeggio chimes at ~6 Hz on
\ channel A, the border cycles black → blue → red ... at 50 Hz, and
\ the screen continuously fills with random uppercase letters.
\
\ Layout:
\   main.fs               entry; clears the screen, inits AY, runs music
\   app/music.fs          tone table, AY register helpers, ISR, music word

require app/music.fs

: main  0 7 cls  music-init  music ;
