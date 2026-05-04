\ Score, level (1..3), and preset-remaining counter.  Hud-dirty is set
\ whenever any of these change so game.fs can repaint the HUD only on
\ frames where it actually needs to.

require core.fs

variable score
variable level
variable preset-remaining
variable hud-dirty
variable game-over-flag

: score-reset        ( -- )    0 score ! ;
: level-set          ( n -- )  level ! ;
: preset-set         ( n -- )  preset-remaining ! ;
: mark-hud-dirty     ( -- )    -1 hud-dirty ! ;
: hud-clean!         ( -- )     0 hud-dirty ! ;

: add-line-score     ( lines -- )
    dup * 100 *  score +!  mark-hud-dirty ;

: dec-preset         ( n -- )
    preset-remaining @ swap - 0 max  preset-remaining !  mark-hud-dirty ;

: level-cleared?     ( -- flag )    preset-remaining @ 0= ;
: advance-level      ( -- )         1 level +!  mark-hud-dirty ;

: set-game-over      ( -- )    -1 game-over-flag ! ;
: clear-game-over    ( -- )     0 game-over-flag ! ;
: game-over?         ( -- flag )    game-over-flag @ ;
