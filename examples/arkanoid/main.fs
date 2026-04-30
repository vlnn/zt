\ Arkanoid-like — paddle and ball with breakable bricks.
\
\ Controls (in an emulator):
\   O — move paddle left
\   P — move paddle right
\
\ Build:  zt build examples/arkanoid/main.fs -o build/arkanoid.sna

require lib/game.fs

: main    arkanoid halt ;
