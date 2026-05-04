\ Moving entities (player, damsels, spreader, bug, wind, Bill) plus
\ the adjacency-count query on the player's cell.  Most actors share
\ the same shape: a current position, a previous position for erase,
\ and an `active` flag.

require core.fs
require input.fs
require rand.fs
require trail.fs

require state.fs
require sounds.fs
require board.fs
require cheat.fs


\ The player
\ ──────────
\ pcol/prow track the live position; prev-col/prev-row store the
\ pre-move position so trail-at can paint the cell the player just
\ left.  player-reset puts the player on the start cell and clears
\ the previous position so the first frame doesn't paint a phantom
\ trail mark.

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


\ Player input
\ ────────────
\ Two control schemes overlap: the digit row 5/6/7/8 with CAPS SHIFT,
\ or the bare 6/7/8/9 keys without.  caps?, plain-key? and
\ shifted-key? combine to detect the four directions; read-dx and
\ read-dy collapse them into ±1 deltas.  apply-input commits the
\ delta to the player's position (clamped) and feeds it to the cheat
\ observer in one pass.

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
: clamp-row      ( n -- n )    0 max start-row min ;

: apply-input    ( -- )
    read-dx read-dy
    2dup cheat-observe
    prow @ + clamp-row prow !
    pcol @ + clamp-col pcol ! ;

: try-move       ( -- moved? )   apply-input moved? ;

: adj-count      ( -- n )      player-xy neighbours4 ;

: player-at?     ( col row -- flag )
    prow @ =  swap pcol @ =  and ;


\ Damsels
\ ───────
\ Two damsels per level on levels 2..8.  pick-damsels scatters them
\ in two horizontal halves of the playfield so they can't both end
\ up in one corner; rescue-damsel triggers when the player walks
\ onto one.

variable damsel1-col  variable damsel1-row
variable damsel2-col  variable damsel2-row
variable damsels-alive

: place-damsel   ( col row -- )
    2dup t-damsel -rot tile!
    damsel-at ;

: pick-damsels   ( -- )
    has-damsels? 0= if 0 damsels-alive ! exit then
    rand-interior  dup damsel1-row !  damsel2-row !
    6 random 6 +   damsel1-col !
    6 random 19 +  damsel2-col !
    damsel1-col @ damsel1-row @ place-damsel
    damsel2-col @ damsel2-row @ place-damsel
    2 damsels-alive ! ;

: rescue-damsel  ( col row -- )
    2dup t-empty -rot tile!
    erase-at
    damsels-alive @ 1- damsels-alive !
    100 score +!
    rescue-chirp ;

: maybe-rescue   ( -- )
    has-damsels? 0= if exit then
    player-xy damsel? if player-xy rescue-damsel then ;


\ The spreader
\ ────────────
\ A 1-in-50 chance per tick to spawn at the left edge on spreader
\ levels.  Once active, it walks rightward one cell per player step,
\ randomly dropping a mine into one of the three rows centred on its
\ own.  It despawns on hitting the right wall or any non-empty cell.

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
    spreader-drop-mine? 0= if exit then
    spreader-col @ spreader-trail-row
    2dup try-place-mine
    reveal-cell-if-mine ;

: spreader-despawn     ( -- )         0 spreader-active ! ;

: spreader-xy          ( -- col row )   spreader-col @ spreader-row @ ;

: spreader-at-edge?    ( -- flag )    spreader-col @ 30 > ;

: spreader-blocked?    ( -- flag )    spreader-xy empty? 0= ;

: spreader-step  ( -- )
    spreader-active @ 0= if exit then
    spreader-xy erase-at
    spreader-maybe-drop
    spreader-col @ 1+ spreader-col !
    spreader-at-edge? if spreader-despawn exit then
    spreader-blocked? if spreader-despawn exit then
    spreader-xy spreader-at ;


\ The bug
\ ───────
\ Stalks the player along the recorded trail at a fixed distance of
\ 12 cells.  Doesn't appear until the trail is long enough; until
\ then it sits invisible.  Catching the player is fatal — the bug's
\ position is read from the trail buffer rather than animated, so
\ the player can outrun it indefinitely on a long enough trail.

variable bug-col  variable bug-row  variable bug-prev-col  variable bug-prev-row
variable bug-active

: bug-follow-distance  ( -- n )   12 ;

: bug-index      ( -- i )
    trail-len@ bug-follow-distance - 0 max ;

: bug-visible?   ( -- flag )
    trail-len@ bug-follow-distance > ;

: bug-xy!        ( col row -- )   bug-row ! bug-col ! ;
: bug-prev-xy!   ( col row -- )   bug-prev-row ! bug-prev-col ! ;
: bug-prev-xy    ( -- col row )   bug-prev-col @ bug-prev-row @ ;

: bug-step       ( -- )
    has-bug? 0= if exit then
    bug-visible? 0= if exit then
    bug-active @ if bug-prev-xy trail-at then
    1 bug-active !
    bug-index trail@ unpack-xy
    2dup bug-xy!
    2dup bug-prev-xy!
    bug-at
    bug-hiss ;

: bug-reset      ( -- )
    0 bug-active !   0 0 bug-xy!  0 0 bug-prev-xy! ;

: player-hit-bug?  ( -- flag )
    bug-active @ 0= if 0 exit then
    bug-col @ bug-row @ player-at? ;


\ The wind
\ ────────
\ On wind levels, after the map-blow threshold, a wind glyph drifts
\ along the trail at a level-dependent rate.  When it catches the
\ player at their current position, the player is pushed — counted
\ as a hit, fatal if it lands on a mine.  The wind reads from the
\ trail buffer the same way the bug does, but at a separate rate.

variable wind-col  variable wind-row
variable wind-prev-col  variable wind-prev-row
variable wind-idx  variable wind-active

: wind-reset     ( -- )
    0 wind-idx !  0 wind-active !
    0 wind-col !  0 wind-row !
    0 wind-prev-col !  0 wind-prev-row ! ;

: wind-due?      ( -- flag )
    has-wind? 0= if 0 exit then
    ti @ map-blow-threshold > 0= if 0 exit then
    ti @ wind-period mod 0= ;

: wind-has-trail?  ( -- flag )   wind-idx @ trail-len@ < ;

: wind-read-position  ( -- )
    wind-idx @ trail@ unpack-xy
    wind-row !  wind-col ! ;

: wind-erase-previous  ( -- )
    wind-active @ 0= if exit then
    wind-prev-col @ wind-prev-row @ trail-at ;

: wind-remember-position  ( -- )
    wind-col @ wind-prev-col !
    wind-row @ wind-prev-row ! ;

: wind-draw      ( -- )
    1 wind-active !
    wind-col @ wind-row @ wind-at
    wind-remember-position ;

: wind-step      ( -- )
    wind-has-trail? 0= if exit then
    wind-erase-previous
    wind-read-position
    wind-idx @ 1+ wind-idx !
    wind-draw ;

: player-hit-by-wind?  ( -- flag )
    wind-active @ 0= if 0 exit then
    wind-col @ wind-row @ player-at? ;


\ Bill
\ ────
\ Final-level boss.  Sits in a chamber with fence walls on either
\ side, leaving only one approach from below; that approach is
\ guarded by a single hidden mine planted three rows down from
\ Bill's position.  Reaching Bill ends the game with the rescue
\ bonus.

variable bill-col
8 constant bill-row

: pick-bill      ( -- )   11 random 11 + bill-col ! ;

: bill-xy        ( -- col row )   bill-col @ bill-row ;

: draw-chamber-wall-row  ( row -- )
    dup  bill-col @ 1-  swap place-fence-cell
         bill-col @ 1+  swap place-fence-cell ;

: draw-chamber-walls  ( -- )
    13 4 do  i bill-row =  0= if i draw-chamber-wall-row then  loop ;

: place-hidden-bill-mine  ( -- )
    bill-col @ bill-row 3 +  try-place-mine ;

: draw-chamber   ( -- )
    draw-chamber-walls
    place-hidden-bill-mine ;

: place-bill     ( -- )
    t-empty bill-xy tile!
    bill-xy bill-at
    draw-chamber ;

: bill?          ( col row -- flag )
    bill-row = swap bill-col @ = and ;
