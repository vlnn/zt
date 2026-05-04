\ Top-level game flow.  The frame loop alternates erase/move/paint
\ phases on a 50 Hz tick.  Gravity ticks every gravity-period frames;
\ inputs throttle through input-period; rotation latches on edge so
\ holding rotate doesn't spin the piece every frame.
\
\ Levels orchestrate as: pf+score reset → load-level (paints presets)
\ → first piece spawn → frame loop until preset-remaining hits 0 or
\ the next spawn fails (game over).

require core.fs
require array.fs
require screen.fs
require sound.fs
require playfield.fs
require pieces.fs
require piece.fs
require controls.fs
require audio.fs
require levels.fs
require score.fs


\ HUD layout
\ ──────────
\ Row 0: SCORE + LEVEL.  Right side cols 22..30 row-by-row used for
\ NEXT preview and PRESET counter.

48 constant ascii-zero

: emit-digit         ( d -- )    ascii-zero + emit ;
: emit-2digits       ( n -- )
    dup 100 mod 10 / emit-digit
    10 mod emit-digit ;
: emit-3digits       ( n -- )
    dup 1000 mod 100 / emit-digit
    dup 100  mod 10  / emit-digit
    10 mod emit-digit ;

: hud-attr-row       ( -- )    $47 0 row-attrs! ;

: hud-print-labels   ( -- )
    0  0 at-xy ." SCORE "
    16 0 at-xy ." LV"
    23 2 at-xy ." NEXT"
    23 8 at-xy ." LEFT" ;

: hud-print-score    ( -- )
    6  0 at-xy score @ emit-3digits ;

: hud-print-level    ( -- )
    19 0 at-xy level @ emit-digit ;

: hud-print-presets  ( -- )
    23 9 at-xy preset-remaining @ emit-3digits ;


\ NEXT-piece preview
\ ──────────────────
\ Drawn into a 4x4 cell window at screen (24, 4).  We blank it first,
\ then walk the next-piece's rotation 0 the same way piece-paint walks
\ the live piece.

24 constant next-screen-col
 4 constant next-screen-row

: next-clear ( -- )
    piece-rows 0 do
        piece-cols 0 do
            empty-tile $00
            i next-screen-col +
            j next-screen-row +
            blit8c
        loop
    loop ;

: next-paint-cell ( br bc -- )
    block-tile
    piece-next-id @ piece-attr
    rot next-screen-col +
    swap next-screen-row +
    blit8c ;

: next-paint ( -- )
    next-clear
    piece-rows 0 do
        piece-cols 0 do
            piece-next-id @ 0 j i piece-cell? if
                j i next-paint-cell
            then
        loop
    loop ;

: draw-hud ( -- )
    hud-print-score
    hud-print-level
    hud-print-presets
    next-paint
    hud-clean! ;

: maybe-draw-hud ( -- )
    hud-dirty @ if draw-hud then ;


\ Field framing
\ ─────────────
\ Walls at cols 10 and 21, plus a bottom row at row 20.  Drawn once at
\ level start.

$47 constant wall-attr
10 constant wall-left-col
21 constant wall-right-col
20 constant wall-bottom-row
 1 constant wall-top-row

: draw-wall-cell  ( col row -- )
    wall-tile wall-attr 2swap blit8c ;

: draw-wall-column ( col -- )
    wall-bottom-row 1+ wall-top-row do
        dup i draw-wall-cell
    loop drop ;

: draw-wall-floor  ( -- )
    wall-right-col 1+ wall-left-col do
        i wall-bottom-row draw-wall-cell
    loop ;

: draw-walls       ( -- )
    wall-left-col  draw-wall-column
    wall-right-col draw-wall-column
    draw-wall-floor ;


\ Input handling
\ ──────────────
\ Move and gravity each have their own throttle counter so different
\ rates compose (e.g. 6 frames per move-step regardless of gravity).
\ Rotation also throttles, but only resets on release so a held button
\ rotates exactly once instead of every input-period frames.

variable move-tick
variable gravity-tick
variable rotate-latched

6 constant move-period
2 constant soft-gravity-period

: gravity-period ( -- p )
    50  level @ 1- 15 *  -  10 max ;

: move-throttle? ( -- ready? )
    move-tick @ 1+ move-tick !
    move-tick @ move-period u<  if 0 exit then
    0 move-tick !  -1 ;

: gravity-throttle? ( -- ready? )
    gravity-tick @ 1+ gravity-tick !
    in-down? if
        gravity-tick @ soft-gravity-period u<  if 0 exit then
    else
        gravity-tick @ gravity-period u<  if 0 exit then
    then
    0 gravity-tick !  -1 ;

: handle-horizontal ( -- )
    move-throttle? 0= if exit then
    in-left?  if -1 0 piece-try-move drop  audio-on-move exit then
    in-right? if  1 0 piece-try-move drop  audio-on-move then ;

: handle-rotate ( -- )
    in-rotate? 0= if 0 rotate-latched ! exit then
    rotate-latched @ if exit then
    -1 rotate-latched !
    piece-try-rotate if audio-on-rotate then ;


\ Locking and line clear
\ ──────────────────────
\ piece-locked goes high when gravity (or hard drop) can't move down.
\ We stamp into the playfield, run pf-compact for line detection, score
\ any cleared lines, decrement preset-remaining by however many preset
\ cells came out, repaint the playfield (cheap — 180 cells), spawn the
\ next piece, and detect game-over via the spawn flag.

: handle-line-clear ( -- )
    pf-cleared-count @ 0= if exit then
    pf-cleared-count @ add-line-score
    pf-presets-cleared @ dec-preset
    audio-on-line-clear
    pf-draw-all ;

: handle-spawn ( -- )
    piece-spawn 0= if set-game-over then ;

: handle-locked ( -- )
    piece-locked @ 0= if exit then
    piece-stamp
    piece-paint
    audio-on-lock
    pf-compact
    handle-line-clear
    0 piece-locked !
    handle-spawn ;


\ Per-frame step and main loop
\ ────────────────────────────
\ Order: erase old piece footprint, run input + gravity, react to lock,
\ paint new piece, refresh HUD if dirty.  The loop terminates on game
\ over OR when the level is cleared (preset-remaining = 0).

: game-step ( -- )
    wait-frame
    piece-erase
    handle-horizontal
    handle-rotate
    gravity-throttle? if piece-gravity-step then
    handle-locked
    piece-paint
    maybe-draw-hud ;

: level-done? ( -- flag )
    game-over? level-cleared? or ;

: game-loop ( -- )
    begin game-step level-done? until ;


\ Level lifecycle
\ ───────────────
\ start-level paints the static parts (background, walls, HUD, NEXT
\ preview seed) and runs the per-frame loop until the level resolves.
\ run-game cycles through the three preset levels; if the player
\ clears all three, end-game-win celebrates; if at any point spawn
\ fails, end-game-lose tolls.

: paint-level ( -- )
    0 0 cls
    hud-attr-row
    hud-print-labels
    draw-walls
    pf-draw-all
    mark-hud-dirty ;

: start-level ( n -- )
    dup level-set
    load-level
    score-reset
    clear-game-over
    0 piece-locked !
    0 move-tick !
    0 gravity-tick !
    0 rotate-latched !
    paint-level
    piece-advance-next
    piece-spawn drop
    piece-paint
    draw-hud
    game-loop ;

: end-game-win ( -- )
    audio-on-level-clear
    20 11 at-xy ." YOU WIN! " ;

: end-game-lose ( -- )
    audio-on-game-over
    20 11 at-xy ." GAME OVER" ;

: run-level ( n -- continue? )
    start-level
    game-over? if 0 exit then
    audio-on-level-clear
    -1 ;

c: level-order   1 2 3 ;

: play-levels ( -- won? )
    level-order a-count 0 do
        level-order i a-byte@ run-level 0= if 0 unloop exit then
    loop -1 ;

: tetris ( -- )
    lock-sprites
    pf-bind
    play-levels if end-game-win else end-game-lose then ;
