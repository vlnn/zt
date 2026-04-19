\ app/actors.fs — moving entities (player, damsels, spreader, bug) and
\ the adjacency-count query on the player's cell.

require core.fs
require input.fs
require rand.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs
require cheat.fs

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

0 constant k-caps

: caps?          ( -- 0|1 )    k-caps pressed? ;
: plain-key?     ( code -- 0|1 )   pressed? caps? 0= and ;
: shifted-key?   ( code -- 0|1 )   pressed? caps? and ;

: move-left?     ( -- 0|1 )    k-left  plain-key?   53 shifted-key?   or ;
: move-right?    ( -- 0|1 )    k-right plain-key?   56 shifted-key?   or ;
: move-up?       ( -- 0|1 )    k-up    plain-key?   55 shifted-key?   or ;
: move-down?     ( -- 0|1 )    k-down  plain-key?   54 shifted-key?   or ;

: read-dx        ( -- dx )     move-right? move-left? - ;
: read-dy        ( -- dy )     move-down?  move-up?   - ;

: clamp-col      ( n -- n )    0 max board-cols 1- min ;
: clamp-row      ( n -- n )    0 max board-rows 1- min ;

: apply-input    ( -- )
    read-dx read-dy
    2dup cheat-observe
    prow @ + clamp-row prow !
    pcol @ + clamp-col pcol ! ;

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

3 constant spreader-drop-odds

: maybe-spawn-spreader  ( -- )
    has-spreader? 0= if exit then
    spreader-active @ if exit then
    50 one-in if
        rand-interior spreader-row !
        3 spreader-col !
        1 spreader-active !
    then ;

: clamp-interior-row   ( row -- row' )
    top-fence-row 1+ max
    bottom-fence-row 1- min ;

: spreader-row-jitter  ( -- -1|0|1 )  3 random 1- ;

: spreader-trail-row   ( -- row )
    spreader-row-jitter spreader-row @ + clamp-interior-row ;

: spreader-drop-mine?  ( -- flag )    spreader-drop-odds one-in ;

: spreader-maybe-drop  ( -- )
    spreader-drop-mine? if
        spreader-col @ spreader-trail-row try-place-mine
    then ;

: spreader-despawn     ( -- )         0 spreader-active ! ;

: spreader-at-edge?    ( -- flag )    spreader-col @ 30 > ;

: spreader-blocked?    ( -- flag )    spreader-col @ spreader-row @ empty? 0= ;

: spreader-step  ( -- )
    spreader-active @ 0= if exit then
    spreader-col @ spreader-row @ erase-at
    spreader-maybe-drop
    spreader-col @ 1+ spreader-col !
    spreader-at-edge? if spreader-despawn exit then
    spreader-blocked? if spreader-despawn exit then
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

: draw-chamber-wall-row  ( row -- )
    >r
    bill-col @ 1-  r@ place-fence-cell
    bill-col @ 1+  r@ place-fence-cell
    r> drop ;

: draw-chamber-walls  ( -- )
    13 4 do  i bill-row =  0= if i draw-chamber-wall-row then  loop ;

: place-hidden-bill-mine  ( -- )
    bill-col @ bill-row 3 +  try-place-mine ;

: draw-chamber   ( -- )
    draw-chamber-walls
    place-hidden-bill-mine ;

: place-bill     ( -- )
    t-empty bill-col @ bill-row tile!
    bill-col @ bill-row bill-at
    draw-chamber ;

: bill?          ( col row -- flag )
    bill-row = swap bill-col @ = and ;
