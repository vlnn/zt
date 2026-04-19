\ Mined-Out — faithful port of Ian Andrew's 1983 BASIC.
\
\ Structural notes:
\   - shadow byte grid (instead of BASIC's SCREEN$ reads)
\   - ASCII chars via EMIT (instead of UDGs — faster primitive path)
\   - BASIC line 520..570 loop structure preserved
\
\ Coordinates:  col = 0..31, row = 0..21. Stack order is always ( col row ).
\ Screen layout:
\   row 0   HUD
\   row 1   top fence with gap at cols 15..16
\   rows 2-19 playfield
\   row 20  bottom fence with gap at cols 15..16
\   row 21  safe area, player start

require core.fs
require rand.fs
require screen.fs
require input.fs
require grid.fs
require sound.fs
require trail.fs

\ ------------------ world constants ------------------

32 constant board-cols
22 constant board-rows
50 constant mine-count

15 constant gap-left
16 constant gap-right
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col

\ tile codes in the shadow grid
0 constant t-empty
1 constant t-mine
2 constant t-fence

\ ascii glyphs
32 constant ch-space
35 constant ch-fence
42 constant ch-mine
79 constant ch-player

\ ------------------ board ------------------

create board-buf  704 allot

: board-init    ( -- )
    board-buf board-cols board-rows grid-set!
    t-empty grid-clear ;

: tile!         ( tag col row -- )   grid! ;
: tile@         ( col row -- tag )   grid@ ;
: empty?        ( col row -- flag )  tile@ t-empty = ;
: fence?        ( col row -- flag )  tile@ t-fence = ;
: mine?         ( col row -- flag )  tile@ t-mine = ;

\ ------------------ drawing one cell ------------------

: put-char      ( ch col row -- )    at-xy emit ;
: erase-at      ( col row -- )       ch-space  -rot put-char ;
: fence-at      ( col row -- )       ch-fence  -rot put-char ;
: mine-at       ( col row -- )       ch-mine   -rot put-char ;
: player-at     ( col row -- )       ch-player -rot put-char ;

\ ------------------ fence ------------------

: gap?          ( col -- flag )      dup gap-left = swap gap-right = or ;

variable _fr
: place-fence-at-col  ( col -- )
    dup gap? 0= if  dup _fr @ t-fence -rot tile!  dup _fr @ fence-at  then
    drop ;

: fence-row     ( row -- )
    _fr !
    board-cols 0 do i place-fence-at-col loop ;

: build-fences  ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row ;

\ ------------------ mines ------------------

: rand-col      ( -- col )   board-cols random ;
: rand-interior ( -- row )   18 random 2 + ;        \ rows 2..19

: try-place-mine  ( col row -- )
    2dup empty? if  t-mine -rot tile!  else  2drop  then ;

: scatter-mines ( n -- )
    0 do rand-col rand-interior try-place-mine loop ;

\ ------------------ player state ------------------

variable px   variable py
variable oldx variable oldy

: player-xy     ( -- col row )   py @ px @ ;
: old-xy        ( -- col row )   oldy @ oldx @ ;
: player-xy!    ( col row -- )   px ! py ! ;
: snapshot-pos  ( -- )           px @ oldx !   py @ oldy ! ;

: player-reset  ( -- )
    start-col start-row player-xy!
    snapshot-pos ;

: moved?        ( -- flag )
    px @ oldx @ <>  py @ oldy @ <> or ;

\ ------------------ input ------------------

54 constant k-left
55 constant k-right
57 constant k-up
56 constant k-down

: setup-keys    ( -- )   k-left k-right k-up k-down set-keys! ;
: read-dx       ( -- dx )   key-right? key-left? - ;
: read-dy       ( -- dy )   key-down?  key-up?   - ;

: clamp-col     ( n -- n )   0 max board-cols 1- min ;
: clamp-row     ( n -- n )   0 max board-rows 1- min ;

: apply-input   ( -- )
    py @ read-dx + clamp-col py !
    px @ read-dy + clamp-row px ! ;

\ ------------------ adjacency (delegates to grid.fs) ------------------

: adj-count     ( -- n )   player-xy neighbours4 ;

\ ------------------ HUD ------------------

: two-digits    ( n -- )
    dup 10 < if 48 emit then . ;

: draw-hud-frame  ( -- )
    0 0 at-xy  ." adj:00  score:00  lvl:1" ;

: draw-adj-hud  ( n -- )
    0 0 at-xy  ." adj:"  two-digits ;

\ ------------------ sounds ------------------

: click         ( -- )       1 30 beep ;

: proximity     ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

: explosion     ( -- )
    40 0 do  2 40 i - beep  loop ;

: fanfare       ( -- )
    10 0 do  3 100 i 10 * - beep  loop ;

\ ------------------ trail / action replay ------------------

1024 constant trail-cells
create trail-buf  2048 allot

: trail-setup   ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

: record-step   ( -- )
    player-xy pack-xy trail-push ;

: replay-delay  ( -- )  3 0 do wait-frame loop ;

: replay-step   ( i -- )
    trail@ unpack-xy 2dup player-at replay-delay erase-at ;

: replay-banner ( -- )
    0 21 at-xy  ." action replay                   " ;

: action-replay ( -- )
    replay-banner
    trail-len@ 0 do i replay-step loop ;

\ ------------------ end-of-level reveal ------------------

variable _mr

: reveal-row    ( row -- )
    _mr !
    board-cols 0 do
        i _mr @ mine? if i _mr @ mine-at then
    loop ;

: show-all-mines  ( -- )
    board-rows 0 do i reveal-row loop ;

\ ------------------ level init ------------------

: init-level    ( -- )
    7 0 cls
    board-init
    build-fences
    mine-count scatter-mines
    player-reset
    trail-setup
    draw-hud-frame
    player-xy player-at ;

\ ------------------ game state ------------------

variable alive
variable score

: die           ( -- )   explosion  0 alive ! ;
: win           ( -- )   fanfare  100 score +!  0 alive ! ;
: throttle      ( frames -- )   0 do wait-frame loop ;

\ ------------------ per-move substeps ------------------

: try-move      ( -- moved? )   apply-input moved? ;

: reveal-player-cell  ( -- )
    player-xy fence? 0= if player-xy mine-at then ;

: handle-collision    ( -- )
    reveal-player-cell die ;

: update-hud    ( -- )   adj-count dup proximity draw-adj-hud ;

: won?          ( -- flag )   px @ 0= ;

\ ------------------ the BASIC 520..570 loop, one tick ------------------

: step-once     ( -- )
    wait-frame
    try-move 0= if exit then
    click
    old-xy erase-at                  \ BASIC 535: erase old cell
    player-xy empty? 0= if  handle-collision exit  then
    player-xy player-at              \ BASIC 550: draw new cell
    update-hud                       \ BASIC 570: adjacency + beep + HUD
    won? if win exit then
    snapshot-pos
    record-step
    4 throttle ;

: play-loop     ( -- )
    1 alive !
    begin alive @ while step-once repeat ;

\ ------------------ end-of-level animation ------------------

: end-of-level  ( -- )
    show-all-mines
    action-replay
    50 throttle ;

\ ------------------ entry ------------------

: init-game     ( -- )
    setup-keys
    0 score !
    1 seed! ;

: main
    init-game
    begin
        init-level
        play-loop
        end-of-level
    again ;
