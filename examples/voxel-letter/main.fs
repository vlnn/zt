\ examples/voxel-letter/main.fs
\
\ Interactive 3D rotation of a row of ZX-Spectrum-font letters.  All
\ letters share the same yaw + pitch — they spin and tilt together —
\ and each is rendered through the same 8-byte back-buffer in turn,
\ then BLIT8'd onto its own char cell.
\
\ Controls:
\   7 / Q   pitch up
\   6 / A   pitch down
\   8 / O   yaw  left
\   9 / P   yaw  right
\   SPACE   quit
\
\ Build:  zt build  examples/voxel-letter/main.fs -o build/voxel.sna

require lib/render.fs
require lib/buffer.fs
require lib/input_voxel.fs

\ angle-yaw, angle-pitch, angle-step, poll-keys, quit? all live in
\ input_voxel.fs.  poll-keys reads keyboard ports directly (~280 T)
\ instead of dispatching through stdlib key-state (~13.9 K T).

\ ── the message ───────────────────────────────────────────────────
\ Up to 5 letters fit at 50 fps.  Each letter occupies one char cell
\ horizontally, spaced 2 cells apart for breathing room.
create letters
    70 c,                              \ F
    79 c,                              \ O
    82 c,                              \ R
    84 c,                              \ T
    72 c,                              \ H

5 constant letter-count

\ Top-row of the letter slot.  All letters share the same row.
11 constant letters-row

\ Leftmost cell column of letter 0.  Centre an N-letter row by setting
\ this to (32 - 2·N) / 2 = (32 - 2·letter-count) / 2.
11 constant letters-col-0

\ ── per-frame work ────────────────────────────────────────────────
\ Bake the rotation once, then for each letter: clear the 8-byte
\ buffer, render the glyph into it, BLIT8 onto that letter's cell.
\ Letters land at columns letters-col-0, letters-col-0 + 2, …
: render-frame  ( -- )
    angle-yaw @  angle-pitch @  bake-rotation
    letter-count 0 do
        clear-buffer
        letters i + c@                 \ ch
        render-letter
        letters-col-0  i 2*  +
        letters-row
        flush-letter
    loop ;

\ A no-op IM 2 handler.  Installing it lets `wait-frame` (ei + halt +
\ di) run safely in the simulator, where there's no ROM at $0038 to
\ catch IM 1 interrupts.  On real hardware a ROM-based IM 1 handler
\ would do the job too.
: frame-isr  ( -- ) ;

: main  ( -- )
    paint-attrs
    0 angle-yaw !
    0 angle-pitch !
    ['] frame-isr im2-handler!
    ei
    begin
        wait-frame                     \ exits with DI — BLIT8 safe
        render-frame
        poll-keys
        quit?
    until
    di
    im2-off
    halt ;
