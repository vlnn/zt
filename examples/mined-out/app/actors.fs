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

\ player's current position
: player-xy      ( -- col row )   pcol @ prow @ ;
\ player's previous position (before this tick)
: old-xy         ( -- col row )   prev-col @ prev-row @ ;
\ store (col, row) as the player's current position
: player-xy!     ( col row -- )   prow ! pcol ! ;
\ remember the current position as the previous one
: snapshot-pos   ( -- )           prow @ prev-row !   pcol @ prev-col ! ;

\ put the player at the start cell and zero the previous position
: player-reset   ( -- )
    start-col start-row player-xy!
    snapshot-pos ;

\ true if the player's position changed since the last snapshot
: moved?         ( -- flag )
    prow @ prev-row @ <>  pcol @ prev-col @ <> or ;

54 constant k-left
55 constant k-right
57 constant k-up
56 constant k-down

0 constant k-caps

\ 1 if the CAPS SHIFT modifier is held
: caps?          ( -- 0|1 )    k-caps pressed? ;
\ 1 if the keycode is held without CAPS SHIFT
: plain-key?     ( code -- 0|1 )   pressed? caps? 0= and ;
\ 1 if the keycode is held while CAPS SHIFT is also held
: shifted-key?   ( code -- 0|1 )   pressed? caps? and ;

\ 1 if the player is requesting a left step (6 or CAPS+5)
: move-left?     ( -- 0|1 )    k-left  plain-key?   53 shifted-key?   or ;
\ 1 if the player is requesting a right step (7 or CAPS+8)
: move-right?    ( -- 0|1 )    k-right plain-key?   56 shifted-key?   or ;
\ 1 if the player is requesting an upward step (9 or CAPS+7)
: move-up?       ( -- 0|1 )    k-up    plain-key?   55 shifted-key?   or ;
\ 1 if the player is requesting a downward step (8 or CAPS+6)
: move-down?     ( -- 0|1 )    k-down  plain-key?   54 shifted-key?   or ;

\ -1, 0, or 1 horizontal step from current input
: read-dx        ( -- dx )     move-right? move-left? - ;
\ -1, 0, or 1 vertical step from current input
: read-dy        ( -- dy )     move-down?  move-up?   - ;

\ clamp a column to [0, board-cols)
: clamp-col      ( n -- n )    0 max board-cols 1- min ;
\ clamp a row to [0, start-row]
: clamp-row      ( n -- n )    0 max start-row min ;

\ apply the current input to player position, also feeding the cheat detector
: apply-input    ( -- )
    read-dx read-dy
    2dup cheat-observe
    prow @ + clamp-row prow !
    pcol @ + clamp-col pcol ! ;

\ try to move; return true if the player's position actually changed
: try-move       ( -- moved? )   apply-input moved? ;

\ count of orthogonal neighbouring mines under the player
: adj-count      ( -- n )      player-xy neighbours4 ;

\ true if (col, row) is the player's current position
: player-at?     ( col row -- flag )
    prow @ =  swap pcol @ =  and ;

variable damsel1-col  variable damsel1-row
variable damsel2-col  variable damsel2-row
variable damsels-alive

\ tag (col, row) as a damsel and draw the glyph
: place-damsel   ( col row -- )
    2dup t-damsel -rot tile!
    damsel-at ;

\ scatter both damsels for this level (or skip on levels without them)
: pick-damsels   ( -- )
    has-damsels? 0= if 0 damsels-alive ! exit then
    rand-interior  dup damsel1-row !  damsel2-row !
    6 random 6 +   damsel1-col !
    6 random 19 +  damsel2-col !
    damsel1-col @ damsel1-row @ place-damsel
    damsel2-col @ damsel2-row @ place-damsel
    2 damsels-alive ! ;

\ rescue a damsel: clear cell, decrement count, award points, chirp
: rescue-damsel  ( col row -- )
    2dup t-empty -rot tile!
    erase-at
    damsels-alive @ 1- damsels-alive !
    100 score +!
    rescue-chirp ;

\ rescue a damsel if the player is standing on one
: maybe-rescue   ( -- )
    has-damsels? 0= if exit then
    player-xy damsel? if player-xy rescue-damsel then ;

variable spreader-col   variable spreader-row   variable spreader-active

3 constant spreader-drop-odds

\ on spreader levels, occasionally spawn a new spreader at the left edge
: maybe-spawn-spreader  ( -- )
    has-spreader? 0= if exit then
    spreader-active @ if exit then
    50 one-in if
        rand-interior spreader-row !
        3 spreader-col !
        1 spreader-active !
    then ;

\ clamp a row to the playable interior between the two fences
: clamp-interior-row   ( row -- row' )
    top-fence-row 1+ max
    bottom-fence-row 1- min ;

\ random row offset for the spreader trail (-1, 0 or 1)
: spreader-row-jitter  ( -- -1|0|1 )  3 random 1- ;

\ next row at which the spreader will drop a mine
: spreader-trail-row   ( -- row )
    spreader-row-jitter spreader-row @ + clamp-interior-row ;

\ true with the configured per-step probability of dropping a mine
: spreader-drop-mine?  ( -- flag )    spreader-drop-odds one-in ;

\ on this step, possibly drop a mine and reveal it
: spreader-maybe-drop  ( -- )
    spreader-drop-mine? 0= if exit then
    spreader-col @ spreader-trail-row       ( col row )
    2dup try-place-mine
    reveal-cell-if-mine ;

\ deactivate the spreader
: spreader-despawn     ( -- )         0 spreader-active ! ;

\ spreader's current position
: spreader-xy          ( -- col row )   spreader-col @ spreader-row @ ;

\ true if the spreader has reached the right side of the board
: spreader-at-edge?    ( -- flag )    spreader-col @ 30 > ;

\ true if the spreader's current cell is non-empty (it should despawn)
: spreader-blocked?    ( -- flag )    spreader-xy empty? 0= ;

\ advance the spreader one cell rightward, dropping a mine and despawning at the edge
: spreader-step  ( -- )
    spreader-active @ 0= if exit then
    spreader-xy erase-at
    spreader-maybe-drop
    spreader-col @ 1+ spreader-col !
    spreader-at-edge? if spreader-despawn exit then
    spreader-blocked? if spreader-despawn exit then
    spreader-xy spreader-at ;

variable bug-col  variable bug-row  variable bug-prev-col  variable bug-prev-row
variable bug-active

\ trail-distance the bug stays behind the player
: bug-follow-distance  ( -- n )   12 ;

\ trail index from which to read the bug's next position
: bug-index      ( -- i )
    trail-len@ bug-follow-distance - 0 max ;

\ true once the trail is long enough for the bug to appear
: bug-visible?   ( -- flag )
    trail-len@ bug-follow-distance > ;

\ store (col, row) as the bug's current position
: bug-xy!        ( col row -- )   bug-row ! bug-col ! ;
\ store (col, row) as the bug's previous position
: bug-prev-xy!   ( col row -- )   bug-prev-row ! bug-prev-col ! ;
\ bug's previous position
: bug-prev-xy    ( -- col row )   bug-prev-col @ bug-prev-row @ ;

\ advance the bug along the trail by one player step
: bug-step       ( -- )
    has-bug? 0= if exit then
    bug-visible? 0= if exit then
    bug-active @ if bug-prev-xy trail-at then
    1 bug-active !
    bug-index trail@ unpack-xy     ( col row )
    2dup bug-xy!
    2dup bug-prev-xy!
    bug-at
    bug-hiss ;

\ deactivate the bug and zero its tracked position
: bug-reset      ( -- )
    0 bug-active !   0 0 bug-xy!  0 0 bug-prev-xy! ;

\ true if the bug shares the player's cell
: player-hit-bug?  ( -- flag )
    bug-active @ 0= if 0 exit then
    bug-col @ bug-row @ player-at? ;

variable wind-col  variable wind-row
variable wind-prev-col  variable wind-prev-row
variable wind-idx  variable wind-active

\ zero out the wind state at the start of a level
: wind-reset     ( -- )
    0 wind-idx !  0 wind-active !
    0 wind-col !  0 wind-row !
    0 wind-prev-col !  0 wind-prev-row ! ;

\ true if a wind step is due this tick
: wind-due?      ( -- flag )
    has-wind? 0= if 0 exit then
    ti @ map-blow-threshold > 0= if 0 exit then
    ti @ wind-period mod 0= ;

\ true while the wind has more trail to traverse
: wind-has-trail?  ( -- flag )   wind-idx @ trail-len@ < ;

\ load the wind's column and row from the trail at the current index
: wind-read-position  ( -- )
    wind-idx @ trail@ unpack-xy
    wind-row !  wind-col ! ;

\ blank the previous wind cell, restoring it as a trail mark
: wind-erase-previous  ( -- )
    wind-active @ 0= if exit then
    wind-prev-col @ wind-prev-row @ trail-at ;

\ remember the wind's position so the next step can erase it
: wind-remember-position  ( -- )
    wind-col @ wind-prev-col !
    wind-row @ wind-prev-row ! ;

\ paint the wind glyph at its current position and remember it
: wind-draw      ( -- )
    1 wind-active !
    wind-col @ wind-row @ wind-at
    wind-remember-position ;

\ advance the wind one trail step
: wind-step      ( -- )
    wind-has-trail? 0= if exit then
    wind-erase-previous
    wind-read-position
    wind-idx @ 1+ wind-idx !
    wind-draw ;

\ true if the wind has reached the player's cell
: player-hit-by-wind?  ( -- flag )
    wind-active @ 0= if 0 exit then
    wind-col @ wind-row @ player-at? ;

variable bill-col
8 constant bill-row

\ pick a random column for Bill within the chamber band
: pick-bill      ( -- )   11 random 11 + bill-col ! ;

\ Bill's coordinates
: bill-xy        ( -- col row )   bill-col @ bill-row ;

\ place fence cells either side of Bill in the given row
: draw-chamber-wall-row  ( row -- )
    dup  bill-col @ 1-  swap place-fence-cell
         bill-col @ 1+  swap place-fence-cell ;

\ build the side walls of Bill's chamber, leaving Bill's row open
: draw-chamber-walls  ( -- )
    13 4 do  i bill-row =  0= if i draw-chamber-wall-row then  loop ;

\ plant the hidden mine guarding Bill's chamber
: place-hidden-bill-mine  ( -- )
    bill-col @ bill-row 3 +  try-place-mine ;

\ draw the chamber walls and the hidden mine
: draw-chamber   ( -- )
    draw-chamber-walls
    place-hidden-bill-mine ;

\ put Bill on the board and build his chamber around him
: place-bill     ( -- )
    t-empty bill-xy tile!
    bill-xy bill-at
    draw-chamber ;

\ true if (col, row) is Bill's cell
: bill?          ( col row -- flag )
    bill-row = swap bill-col @ = and ;
