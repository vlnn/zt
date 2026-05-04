\ Bach Two-Part Invention No. 4 in D minor, BWV 775, arranged for the
\ AY-3-8912.  Voice 1 (right hand) plays on channel A; voice 2 (left
\ hand) on channel B.  Channel C is silenced.  The score data lives in
\ app/song-data.fs and was transcribed from the Mutopia LilyPond source
\ (typeset by Allen Garvin, public domain) — 312 16th-note steps
\ spanning 52 bars in 3/8.
\
\ The IM 2 ISR advances one 16th note every 8 frames (50 Hz / 8 = 6.25
\ Hz step rate, so a sixteenth = 160 ms, a quarter = 640 ms, ~94 bpm).
\ While the music plays the foreground keeps cycling the border and
\ spewing random letters, just like im2-music — proving the ISR is a
\ well-behaved colon word that doesn't disturb the main thread.
\
\ Build (must be 128k — AY is 128k-only):
\   uv run python -m zt.cli build examples/im2-bach/main.fs \
\       -o build/im2-bach.sna --target 128k --include-dir examples
\
\ Layout:
\   main.fs               entry; clears the screen, runs music
\   app/music.fs          AY driver, ISR, song player
\   app/song-data.fs      312-step BWV 775 score (auto-generated)
\   source/               upstream LilyPond source for reproducibility
\   tools/                LilyPond → song-data.fs transcriber + tests

require app/music.fs

: main  0 7 cls  music ;
