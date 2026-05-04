\ Arkanoid-like — paddle and ball with breakable bricks.  Controls are
\ O to move the paddle left, P to move right; the ball loses a life
\ when it falls below the paddle row, and clearing the brick wall
\ refills it for another go.
\
\ Build:  zt build examples/arkanoid/main.fs -o build/arkanoid.sna
\
\ Module layout:
\   sprites.fs   pixel data (ball, paddle, bricks, walls)
\   score.fs     score / lives / hud-dirty state
\   bricks.fs    30x4 brick grid, hit detection
\   paddle.fs    3-cell paddle, O/P input, velocity tracking
\   ball.fs      pixel-resolution physics, zone-based paddle bounce
\   game.fs      per-frame loop, screen restoration, top-level entry

require lib/game.fs

: main    arkanoid halt ;
