\ Mined-Out — faithful port of Ian Andrew's 1983 BASIC.
\
\ Shadow grid for collision, ASCII glyphs via EMIT for speed.
\ BASIC lines 520..570 drive the per-move loop.
\
\ Coordinates:  col = 0..31, row = 0..21. Stack order is always ( col row ).
\ Screen:
\   row 0     HUD
\   row 1     top fence, gap at cols 15..16
\   rows 2-19 playfield
\   row 20    bottom fence, gap at cols 15..16
\   row 21    safe area, player start

require core.fs
require rand.fs
require screen.fs
require input.fs
require grid.fs
require sound.fs
require trail.fs

32 constant board-cols
22 constant board-rows

15 constant gap-left
16 constant gap-right
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col

0 constant t-empty
1 constant t-mine
2 constant t-fence
3 constant t-damsel

32 constant ch-space
35 constant ch-fence
42 constant ch-mine
79 constant ch-player
63 constant ch-damsel
37 constant ch-spreader
64 constant ch-bug

\ Eight-level parameter tables; entries 0..7 match levels 1..8.
\ BASIC's level 9 (Bill rescue) isn't included yet.
create level-paper    6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c, 6 c,
create level-border   0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 0 c, 2 c,
create level-mines   50 c, 60 c, 70 c, 80 c, 90 c, 100 c, 20 c, 50 c,
create level-bonus    0 , 250 , 750 , 1500 , 2200 , 2700 , 3500 , 4200 ,

variable level-no
variable alive
variable score

\ Current level as a zero-based table index.
: lx             ( -- i )   level-no @ 1- ;

: level-paper@   ( -- p )   level-paper  lx + c@ ;
: level-border@  ( -- b )   level-border lx + c@ ;
: level-mines@   ( -- m )   level-mines  lx + c@ ;
: level-bonus@   ( -- n )   level-bonus  lx 2 * + @ ;

\ True when the current level is at least n.
: level>=?       ( n -- flag )   level-no @ swap < 0= ;
: has-damsels?   ( -- flag )     2 level>=? ;
: has-spreader?  ( -- flag )     3 level>=? ;
: has-bug?       ( -- flag )     4 level>=? ;

create board-buf  704 allot

\ Wire the shadow grid to our buffer and zero it out.
: board-init     ( -- )
    board-buf board-cols board-rows grid-set!
    t-empty grid-clear ;

: tile!          ( tag col row -- )   grid! ;
: tile@          ( col row -- tag )   grid@ ;
: empty?         ( col row -- flag )  tile@ t-empty = ;
: fence?         ( col row -- flag )  tile@ t-fence = ;
: mine?          ( col row -- flag )  tile@ t-mine = ;
: damsel?        ( col row -- flag )  tile@ t-damsel = ;

: put-char       ( ch col row -- )    at-xy emit ;
: erase-at       ( col row -- )       ch-space    -rot put-char ;
: fence-at       ( col row -- )       ch-fence    -rot put-char ;
: mine-at        ( col row -- )       ch-mine     -rot put-char ;
: player-at      ( col row -- )       ch-player   -rot put-char ;
: damsel-at      ( col row -- )       ch-damsel   -rot put-char ;
: spreader-at    ( col row -- )       ch-spreader -rot put-char ;
: bug-at         ( col row -- )       ch-bug      -rot put-char ;

: gap?           ( col -- flag )      dup gap-left = swap gap-right = or ;

variable _fr

\ Place one fence cell at (col, _fr) unless the column is a gap.
: place-fence-at-col  ( col -- )
    dup gap? 0= if
        dup _fr @ t-fence -rot tile!
        dup _fr @ fence-at
    then drop ;

\ Fill one row with fence tiles, respecting the gap.
: fence-row      ( row -- )
    _fr !
    board-cols 0 do i place-fence-at-col loop ;

: build-fences   ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row ;

: rand-col       ( -- col )   board-cols random ;
: rand-interior  ( -- row )   18 random 2 + ;        \ rows 2..19

\ Drop a mine on an empty cell; silently skip otherwise.
: try-place-mine    ( col row -- )
    2dup empty? if t-mine -rot tile! else 2drop then ;

: scatter-mines  ( n -- )
    0 do rand-col rand-interior try-place-mine loop ;

variable px   variable py
variable oldx variable oldy

: player-xy      ( -- col row )   py @ px @ ;
: old-xy         ( -- col row )   oldy @ oldx @ ;
: player-xy!     ( col row -- )   px ! py ! ;
: snapshot-pos   ( -- )           px @ oldx !   py @ oldy ! ;

: player-reset   ( -- )
    start-col start-row player-xy!
    snapshot-pos ;

: moved?         ( -- flag )
    px @ oldx @ <>  py @ oldy @ <> or ;

54 constant k-left
55 constant k-right
57 constant k-up
56 constant k-down

: setup-keys     ( -- )        k-left k-right k-up k-down set-keys! ;
: read-dx        ( -- dx )     key-right? key-left? - ;
: read-dy        ( -- dy )     key-down?  key-up?   - ;

: clamp-col      ( n -- n )    0 max board-cols 1- min ;
: clamp-row      ( n -- n )    0 max board-rows 1- min ;

\ Read the four direction keys and update px/py.
: apply-input    ( -- )
    py @ read-dx + clamp-col py !
    px @ read-dy + clamp-row px ! ;

\ BASIC: o = count of 4-adjacent non-empty cells.  Delegates to grid.fs.
: adj-count      ( -- n )      player-xy neighbours4 ;

: two-digits     ( n -- )
    dup 10 < if 48 emit then . ;

\ The HUD is redrawn in full every move — EMIT is a primitive and this
\ runs at most once per step, so the cost is negligible.
: draw-hud       ( -- )
    0 0 at-xy
    ." adj:"   adj-count two-digits
    ."   score:" score @ .
    ."   lvl:"   level-no @ . ;

: click          ( -- )        1 30 beep ;

\ Pitch the beep by distance-to-mines: silent on 0 neighbours.
: proximity      ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

: explosion      ( -- )
    40 0 do  2 40 i - beep  loop ;

: fanfare        ( -- )
    10 0 do  3 100 i 10 * - beep  loop ;

: rescue-chirp   ( -- )
    8 0 do  2 30 i 8 * + beep  loop ;

: bug-hiss       ( -- )  1 100 beep ;

1024 constant trail-cells
create trail-buf  2048 allot

\ Reset the trail to empty; call at the start of each level.
: trail-setup    ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

: record-step    ( -- )        player-xy pack-xy trail-push ;

: replay-delay   ( -- )        3 0 do wait-frame loop ;
: throttle       ( frames -- ) 0 do wait-frame loop ;

\ Draw the player at trail[i], pause, erase.
: replay-step    ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

: replay-banner  ( -- )
    0 21 at-xy  ." action replay                   " ;

: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do i replay-step loop ;

variable _mr

\ For one row, draw the glyph of every hidden mine it contains.
: reveal-row     ( row -- )
    _mr !
    board-cols 0 do
        i _mr @ mine? if i _mr @ mine-at then
    loop ;

: show-all-mines ( -- )
    board-rows 0 do i reveal-row loop ;

variable damsel1-col  variable damsel1-row
variable damsel2-col  variable damsel2-row
variable damsels-alive

\ Put a damsel tile + glyph on the given empty cell.
: place-damsel   ( col row -- )
    2dup t-damsel -rot tile!
    2dup damsel-at
    2drop ;

\ BASIC lines 450-480: two damsels on the same row, different random columns.
: pick-damsels   ( -- )
    has-damsels? 0= if 0 damsels-alive ! exit then
    rand-interior damsel1-row !
    damsel1-row @ damsel2-row !
    6 random 6 +  damsel1-col !
    6 random 19 + damsel2-col !
    damsel1-col @ damsel1-row @ place-damsel
    damsel2-col @ damsel2-row @ place-damsel
    2 damsels-alive ! ;

variable spreader-col   variable spreader-row   variable spreader-active

\ BASIC: 1-in-50 chance the spreader wakes up on this tick.
: maybe-spawn-spreader  ( -- )
    has-spreader? 0= if exit then
    spreader-active @ if exit then
    50 one-in if
        rand-interior spreader-row !
        3 spreader-col !
        1 spreader-active !
    then ;

\ One cell of spreader motion: place a mine behind, advance, draw.
: spreader-step  ( -- )
    spreader-active @ 0= if exit then
    spreader-col @ spreader-row @ erase-at
    spreader-col @ spreader-row @ try-place-mine
    spreader-col @ 1+ spreader-col !
    spreader-col @ 30 > if 0 spreader-active ! exit then
    spreader-col @ spreader-row @ empty? 0= if 0 spreader-active ! exit then
    spreader-col @ spreader-row @ spreader-at ;

variable bug-col  variable bug-row  variable bug-prev-col  variable bug-prev-row
variable bug-active

\ Bug follows the player's trail at a fixed offset.  Lower = closer.
: bug-follow-distance  ( -- n )   12 ;

: bug-index      ( -- i )
    trail-len@ bug-follow-distance - 0 max ;

: bug-visible?   ( -- flag )
    trail-len@ bug-follow-distance > ;

: bug-step       ( -- )
    has-bug? 0= if exit then
    bug-visible? 0= if exit then
    bug-active @ if
        bug-prev-col @ bug-prev-row @ erase-at
    then
    1 bug-active !
    bug-index trail@ unpack-xy 2dup bug-row ! bug-col !
    bug-at
    bug-col @ bug-prev-col !
    bug-row @ bug-prev-row !
    bug-hiss ;

: bug-reset      ( -- )
    0 bug-active !   0 bug-col !   0 bug-row !
    0 bug-prev-col !  0 bug-prev-row ! ;

: die            ( -- )   explosion  0 alive ! ;

\ BASIC rescue: erase damsel, bonus score, chirp.
: rescue-damsel  ( col row -- )
    2dup t-empty -rot tile!
    2dup erase-at
    2drop
    damsels-alive @ 1- damsels-alive !
    100 score +!
    rescue-chirp ;

: maybe-rescue   ( -- )
    has-damsels? 0= if exit then
    player-xy damsel? if player-xy rescue-damsel then ;

\ Level-complete bonus scales with the current level's entry.
: award-bonus    ( -- )   level-bonus@ score +! ;

: advance-level  ( -- )
    level-no @ 1+ 8 min level-no ! ;

: win            ( -- )   fanfare award-bonus 100 score +!  0 alive ! ;

: try-move       ( -- moved? )   apply-input moved? ;

\ On death: draw a mine at the player cell unless we stepped onto a fence.
: reveal-player-cell  ( -- )
    player-xy fence? 0= if player-xy mine-at then ;

: handle-collision  ( -- )
    reveal-player-cell die ;

: update-hud     ( -- )
    adj-count proximity
    draw-hud ;

: won?           ( -- flag )     px @ 0= ;

\ Did the player just land on the bug's current cell?
: player-hit-bug?  ( -- flag )
    bug-active @ 0= if 0 exit then
    py @ bug-col @ =  px @ bug-row @ =  and ;

\ One iteration of the BASIC 520..570 loop.
: step-once      ( -- )
    wait-frame
    maybe-spawn-spreader
    spreader-step
    try-move 0= if exit then
    click
    old-xy erase-at
    maybe-rescue
    player-xy empty? 0= if handle-collision exit then
    player-xy player-at
    update-hud
    won? if win exit then
    snapshot-pos
    record-step
    bug-step
    player-hit-bug? if die exit then
    4 throttle ;

: play-loop      ( -- )
    1 alive !
    begin alive @ while step-once repeat ;

\ Apply paper/border colours for the current level.
: apply-level-colors  ( -- )
    level-paper@ 0 cls
    level-border@ border ;

\ Fresh board setup for whichever level-no is currently set.
: init-level     ( -- )
    apply-level-colors
    board-init
    build-fences
    level-mines@ scatter-mines
    pick-damsels
    bug-reset
    0 spreader-active !
    player-reset
    trail-setup
    draw-hud
    player-xy player-at ;

\ Reveal, replay, pause — BASIC's between-levels flourish.
: end-of-level   ( -- )
    show-all-mines
    action-replay
    50 throttle ;

: init-game      ( -- )
    setup-keys
    0 score !
    1 level-no !
    1 seed! ;

\ Top-level: run levels forever, advancing on win, restarting on death.
: main
    init-game
    begin
        init-level
        play-loop
        end-of-level
        won? if advance-level then
    again ;
