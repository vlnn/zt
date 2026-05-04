\ Showcase for the five SP-stream sprite primitives, one row each.
\ Renders a frame's worth of sprites and halts — there's no animation,
\ just visible output of every blit variant the runtime ships:
\
\   row 2  (chars):  blit8       8x8 BW, char-aligned
\   row 5  (chars):  blit8c      8x8 colored, char-aligned
\   y = 64 (px):     blit8x      8x8 BW, pixel xy
\   y = 96 (px):     blit8xc     8x8 colored, pixel xy
\   y = 144 (px):    multi-blit  composite spaceship (nose + body + tail)
\
\ Build:  zt build examples/sprite-demo/main.fs -o build/sprite-demo.sna

require lib/sprites-data.fs

: demo-blit8
    smiley 4  2 blit8
    smiley 8  2 blit8
    smiley 12 2 blit8
    smiley 16 2 blit8 ;

: demo-blit8c
    smiley $46 4  5 blit8c
    smiley $42 8  5 blit8c
    smiley $44 12 5 blit8c
    smiley $47 16 5 blit8c ;

: demo-blit8x
    smiley-shifted 32  64 blit8x
    smiley-shifted 66  64 blit8x
    smiley-shifted 100 64 blit8x
    smiley-shifted 134 64 blit8x ;

: demo-blit8xc
    smiley-shifted $44 35  96 blit8xc
    smiley-shifted $42 75  96 blit8xc
    smiley-shifted $45 115 96 blit8xc
    smiley-shifted $43 155 96 blit8xc ;

: demo-multi
    ship-table 16 144 multi-blit
    ship-table 80 144 multi-blit ;

\ No unlock-sprites before halt: that would re-enable interrupts, and a
\ frame-loop program would call it at the right moment.  Here we lock
\ once and freeze with the picture on screen.

: main
    7 0 cls
    lock-sprites
    demo-blit8
    demo-blit8c
    demo-blit8x
    demo-blit8xc
    demo-multi
    halt ;
