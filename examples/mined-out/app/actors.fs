\ app/actors.fs — moving entities (player, damsels, spreader, bug) and
\ the adjacency-count query on the player's cell.

require core.fs
require input.fs
require rand.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs

variable prow   variable pcol
variable prev-row variable prev-col

: player-xy      ( -- col row )   pcol @ prow @ ;
: old-xy         ( -- col row )   prev-col @ prev-row @ ;
: player-xy!     ( col row -- )   prow ! pcol ! ;
: snapshot-pos   ( -- )           prow @ prev-row !   pcol @ prev-col ! ;

: player-reset   ( -- )
    start-col start-row player-xy!
    snapshot-pos ;

: moved?         ( -- flag )
    prow @ prev-row @ <>  pcol @ prev-col @ <> or ;

54 constant k-left
55 constant k-right
57 constant k-up
56 constant k-down

: setup-keys     ( -- )        k-left k-right k-up k-down set-keys! ;
: read-dx        ( -- dx )     key-right? key-left? - ;
: read-dy        ( -- dy )     key-down?  key-up?   - ;

: clamp-col      ( n -- n )    0 max board-cols 1- min ;
: clamp-row      ( n -- n )    0 max board-rows 1- min ;

: apply-input    ( -- )
    pcol @ read-dx + clamp-col pcol !
    prow @ read-dy + clamp-row prow ! ;

: try-move       ( -- moved? )   apply-input moved? ;

: adj-count      ( -- n )      player-xy neighbours4 ;

variable damsel1-col  variable damsel1-row
variable damsel2-col  variable damsel2-row
variable damsels-alive

: place-damsel   ( col row -- )
    2dup t-damsel -rot tile!
    2dup damsel-at
    2drop ;

: pick-damsels   ( -- )
    has-damsels? 0= if 0 damsels-alive ! exit then
    rand-interior damsel1-row !
    damsel1-row @ damsel2-row !
    6 random 6 +  damsel1-col !
    6 random 19 + damsel2-col !
    damsel1-col @ damsel1-row @ place-damsel
    damsel2-col @ damsel2-row @ place-damsel
    2 damsels-alive ! ;

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

variable spreader-col   variable spreader-row   variable spreader-active

: maybe-spawn-spreader  ( -- )
    has-spreader? 0= if exit then
    spreader-active @ if exit then
    50 one-in if
        rand-interior spreader-row !
        3 spreader-col !
        1 spreader-active !
    then ;

: spreader-row-jitter  ( -- -1|0|1 )  3 random 1- ;
: spreader-trail-row   ( -- row )     spreader-row-jitter spreader-row @ + ;

: spreader-step  ( -- )
    spreader-active @ 0= if exit then
    spreader-col @ spreader-row @ erase-at
    spreader-col @ spreader-trail-row try-place-mine
    spreader-col @ 1+ spreader-col !
    spreader-col @ 30 > if 0 spreader-active ! exit then
    spreader-col @ spreader-row @ empty? 0= if 0 spreader-active ! exit then
    spreader-col @ spreader-row @ spreader-at ;

variable bug-col  variable bug-row  variable bug-prev-col  variable bug-prev-row
variable bug-active

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

: player-hit-bug?  ( -- flag )
    bug-active @ 0= if 0 exit then
    pcol @ bug-col @ =  prow @ bug-row @ =  and ;

variable bill-col
8 constant bill-row

: pick-bill      ( -- )   11 random 6 +  5 +  bill-col ! ;

: place-chamber-cell  ( col row -- )
    2dup t-fence -rot tile!
    fence-at ;

: draw-chamber-bar-at-row  ( row -- )
    >r
    bill-col @ 1-  r@ place-chamber-cell
    bill-col @     r@ place-chamber-cell
    bill-col @ 1+  r@ place-chamber-cell
    r> drop ;

: draw-chamber   ( -- )
    7 draw-chamber-bar-at-row
    9 draw-chamber-bar-at-row ;

: place-bill     ( -- )
    t-empty bill-col @ bill-row tile!
    bill-col @ bill-row bill-at
    draw-chamber ;

: bill?          ( col row -- flag )
    bill-row = swap bill-col @ = and ;
