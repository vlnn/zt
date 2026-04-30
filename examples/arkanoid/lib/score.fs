\ Score and lives state for arkanoid.
\
\ hud-dirty is a one-bit flag set by add-brick / lose-life. game.fs reads
\ it once per frame and only repaints the HUD digits when set, so a
\ stationary score doesn't pay the cost of digit emit on every frame.

require core.fs

variable score
variable lives
variable hud-dirty

3   constant lives-start
10  constant brick-points

: score-reset    ( -- )    0 score ! ;
: lives-reset    ( -- )    lives-start lives ! ;
: mark-hud-dirty ( -- )    -1 hud-dirty ! ;
: hud-clean!     ( -- )     0 hud-dirty ! ;
: scoring-reset  ( -- )    score-reset lives-reset mark-hud-dirty ;

: add-brick      ( -- )    brick-points score +! mark-hud-dirty ;
: lose-life      ( -- )    -1 lives +! mark-hud-dirty ;
: dead?          ( -- flag )    lives @ 0= ;
