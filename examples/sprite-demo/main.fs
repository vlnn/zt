\ Sprite primitives demo.
\
\ Shows the five SP-stream sprite primitives, one row each:
\   row 2  (chars):  BLIT8       \ 8x8 BW, char-aligned
\   row 5  (chars):  BLIT8C      \ 8x8 colored, char-aligned
\   y=64   (px):     BLIT8X      \ 8x8 BW, pixel xy
\   y=96   (px):     BLIT8XC     \ 8x8 colored, pixel xy
\   y=144  (px):     MULTI-BLIT  \ composite spaceship (nose + body + tail)
\
\ Build:  zt build examples/sprite-demo/main.fs -o build/sprite-demo.sna

require lib/sprites-data.fs

: demo-blit8                          \ char row 2: plain BW smileys
    smiley 4  2 blit8
    smiley 8  2 blit8
    smiley 12 2 blit8
    smiley 16 2 blit8 ;

: demo-blit8c                         \ char row 5: colored smileys
    smiley $46 4  5 blit8c            \ bright cyan ink
    smiley $42 8  5 blit8c            \ red ink
    smiley $44 12 5 blit8c            \ green ink
    smiley $47 16 5 blit8c ;          \ white ink

: demo-blit8x                         \ y=64: pixel-shifted BW row
    smiley-shifted 32  64 blit8x
    smiley-shifted 66  64 blit8x
    smiley-shifted 100 64 blit8x
    smiley-shifted 134 64 blit8x ;

: demo-blit8xc                        \ y=96: pixel-shifted colored row
    smiley-shifted $44 35  96 blit8xc
    smiley-shifted $42 75  96 blit8xc
    smiley-shifted $45 115 96 blit8xc
    smiley-shifted $43 155 96 blit8xc ;

: demo-multi                          \ y=144: two 24x8 spaceships
    ship-table 16 144 multi-blit
    ship-table 80 144 multi-blit ;

: main
    7 0 cls
    init-ship-table
    lock-sprites
    demo-blit8
    demo-blit8c
    demo-blit8x
    demo-blit8xc
    demo-multi
    \ Note: no UNLOCK-SPRITES — we halt right away. In a frame-loop program
    \ you would call UNLOCK-SPRITES here so interrupts can run.
    halt ;
