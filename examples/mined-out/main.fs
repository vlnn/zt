\ Mined-Out — faithful port of Ian Andrew's 1983 BASIC.
\
\ Structural differences from BASIC kept minimal:
\   - we use a shadow byte grid instead of SCREEN$(x,y) reads
\   - ASCII chars via EMIT for speed instead of UDGs
\   - otherwise the loop structure mirrors BASIC lines 520..570
\
\ Coordinates match BASIC: x is row (0..21), y is col (0..31).
\ Screen layout:
\   row 0   HUD
\   row 1   top fence, gap at cols 15..16
\   rows 2-19 playfield
\   row 20  bottom fence, gap at cols 15..16
\   row 21  safe area, player starts at col 15

require core.fs
require rand.fs
require screen.fs
require input.fs
require grid.fs
require sound.fs
require trail.fs

32 constant screen-cols
22 constant screen-rows

\ tile codes held in the shadow grid
0 constant t-empty
1 constant t-mine
2 constant t-fence

\ ascii glyphs for rendering
32 constant ch-space
35 constant ch-fence           \ '#'
42 constant ch-mine            \ '*'
79 constant ch-player          \ 'O'

15 constant gap-left
16 constant gap-right
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col

50 constant mine-count

create board-buf  704 allot    \ 32 * 22
: board-init  ( -- )  board-buf screen-cols screen-rows grid-set!  t-empty grid-clear ;

\ ------------------ drawing one cell ------------------

: put-char   ( ch col row -- )  at-xy emit ;
: erase-at   ( col row -- )     ch-space -rot put-char ;
: fence-at   ( col row -- )     ch-fence -rot put-char ;
: mine-at    ( col row -- )     ch-mine  -rot put-char ;
: player-at  ( col row -- )     ch-player -rot put-char ;

\ ------------------ board setup ------------------

variable _fr

: is-gap?       ( col -- flag )   dup gap-left = swap gap-right = or ;
: fence-cell    ( col row -- )
    2dup t-fence -rot grid!
    fence-at ;

: fence-row     ( row -- )
    _fr !
    screen-cols 0 do
        i is-gap? 0= if i _fr @ fence-cell then
    loop ;

: build-fences  ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row ;

\ ------------------ mine scattering ------------------

: rand-col         ( -- col )   screen-cols random ;
: rand-play-row    ( -- row )   18 random 2 + ;         \ rows 2..19

: place-mine-at    ( col row -- )
    2dup grid@ t-empty = if
        t-mine -rot grid!
    else
        2drop
    then ;

: scatter-mines    ( n -- )
    0 do rand-col rand-play-row place-mine-at loop ;

\ ------------------ player state ------------------

variable px   variable py            \ BASIC x=row, y=col
variable oldx variable oldy

: player-reset  ( -- )
    start-col py !   start-row px !
    start-col oldy ! start-row oldx ! ;

: xy-now     ( -- col row )   py @ px @ ;
: xy-old     ( -- col row )   oldy @ oldx @ ;

\ ------------------ keys (BASIC: "6789") ------------------

54 constant k-left
55 constant k-right
57 constant k-up                     \ BASIC had 8=up, 9=down; user prefers 9=up, 8=down
56 constant k-down

: setup-keys  ( -- )   k-left k-right k-up k-down set-keys! ;

: read-dx    ( -- dx )   key-right? key-left? - ;
: read-dy    ( -- dy )   key-down?  key-up?   - ;

: clamp-col  ( n -- n )   0 max screen-cols 1- min ;
: clamp-row  ( n -- n )
    dup 22 = if drop 21 exit then   \ BASIC: x = x - (x=22)
    0 max 21 min ;

: apply-input  ( -- )
    py @ read-dx + clamp-col py !
    px @ read-dy + clamp-row px ! ;

: moved?     ( -- flag )
    px @ oldx @ <>  py @ oldy @ <> or ;

: snapshot-pos  ( -- )   px @ oldx !   py @ oldy ! ;

\ ------------------ adjacency ------------------

: non-empty?  ( col row -- 0|1 )  grid@ 0= 0= 1 and ;

: adj-count   ( -- n )
    py @ px @ 1- non-empty?
    py @ px @ 1+ non-empty? +
    py @ 1- px @ non-empty? +
    py @ 1+ px @ non-empty? + ;

\ ------------------ HUD ------------------

: two-digits  ( n -- )
    dup 10 < if 48 emit then . ;

: draw-adj-hud  ( n -- )
    0 0 at-xy  ." adj:"  two-digits ;

: draw-score-hud  ( score -- )
    10 0 at-xy  ." score:"  two-digits ;

\ ------------------ sounds ------------------

: click       ( -- )   1 30 beep ;
: proximity   ( n -- )
    dup 0= if drop exit then
    2 swap 10 * beep ;

: explosion   ( -- )
    40 0 do  2 40 i - beep  loop ;

: fanfare     ( -- )
    10 0 do  3 100 i 10 * - beep  loop ;

\ ------------------ movement trail for action replay ------------------

1024 constant trail-cells
create trail-buf  2048 allot

: init-trail     ( -- )
    trail-buf trail-cells trail-init
    trail-reset ;

: record-step    ( -- )
    py @ px @ pack-xy trail-push ;

\ ------------------ end-of-level reveal ------------------

variable _mr

: reveal-row     ( row -- )
    _mr !
    screen-cols 0 do
        i _mr @ grid@ t-mine = if i _mr @ mine-at then
    loop ;

: show-all-mines  ( -- )
    screen-rows 0 do i reveal-row loop ;

: replay-delay   ( -- )  3 0 do wait-frame loop ;

: replay-step    ( idx -- )
    trail@ unpack-xy                     ( col row )
    2dup player-at
    replay-delay
    erase-at ;

: replay-banner  ( -- )
    0 21 at-xy  ." action replay                   " ;

: action-replay  ( -- )
    replay-banner
    trail-len@ 0 do i replay-step loop ;

: draw-hud-frame  ( -- )
    0 0 at-xy  ." adj:00  score:00  lvl:1" ;

: init-level  ( -- )
    7 0 cls
    board-init
    build-fences
    mine-count scatter-mines
    player-reset
    init-trail
    draw-hud-frame
    xy-now player-at ;

\ ------------------ game loop ------------------

variable alive
variable score

: collide?    ( -- flag )  xy-now grid@ t-empty <> ;

: at-top?     ( -- flag )  px @ 0= ;

: throttle  ( frames -- )  0 do wait-frame loop ;

: step-once   ( -- )
    wait-frame
    \ BASIC line 520: read input, update px/py
    apply-input
    moved? 0= if exit then
    click
    \ BASIC line 535: erase old, check new
    xy-old erase-at
    collide? if
        xy-now
        py @ px @ t-fence = if drop drop explosion  0 alive ! exit then  \ walked into fence
        drop drop
        xy-now mine-at
        explosion
        0 alive !
        exit
    then
    \ BASIC line 550: draw at new
    xy-now player-at
    \ BASIC line 570: adjacency, win check
    adj-count dup proximity draw-adj-hud
    at-top? if
        fanfare
        100 score +!
        0 alive !
        exit
    then
    snapshot-pos
    record-step
    4 throttle ;

: play-loop   ( -- )
    1 alive !
    begin  alive @  while  step-once  repeat ;

\ ------------------ entry ------------------

: init-game    ( -- )
    setup-keys
    0 score !
    1 seed! ;

: end-of-level  ( -- )
    show-all-mines
    action-replay
    50 0 do wait-frame loop ;       \ 1s pause before restart

: main
    init-game
    begin
        init-level
        play-loop
        end-of-level
    again ;
