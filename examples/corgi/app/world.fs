\ The static world: items, directions, rooms, the corridors between them,
\ and where things start out.  Run-time mutable state — the player's
\ location and where each item is — lives here too, since every query
\ touches it.

require core.fs
require array-hof.fs


\ Items
\ ─────
\ Three items, ids 0..2.  Ids double as indices into every per-item
\ array (item-loc, item-homes, item-printers).  Adding an item means
\ defining a new constant and adding one entry to each.

0 constant bone
1 constant stick
2 constant ball


\ Item locations
\ ──────────────
\ An item lives in exactly one place: a room (its address), the player's
\ jaws (`carried`), or `nowhere`.  Both sentinels are negative so they
\ can't collide with a real address.  -1 also serves as the "blocked
\ exit" marker further down — same byte pattern, same meaning of
\ "absent", same `blocked?` test if you squint.

-1 constant nowhere
-2 constant carried


\ Directions
\ ──────────
\ A direction is a cell index into a room's .exits array, so we get
\ four slots per room.  The numbering is deliberate: dir-n/dir-s share
\ the low pair (0/1) and dir-e/dir-w the high pair (2/3).  Flipping
\ bit 0 walks across each axis without a lookup table.

0 constant dir-n
1 constant dir-s
2 constant dir-e
3 constant dir-w

: opposite-dir   ( dir -- dir' )   1 xor ;


\ Room descriptions
\ ─────────────────
\ One word per room, called from `describe-room` over in game.fs.
\ Defined here, before the room records, so each record can capture
\ the description's xt at compile time — there's no late binding.

: kitchen-desc
    ." You are in your warm kitchen." cr
    ." Your bowl smells faintly of dinner." cr
    ." A bright hallway lies to the NORTH." cr ;

: hallway-desc
    ." A sunny hallway." cr
    ." The kitchen is to the SOUTH." cr
    ." The front door stands open NORTH to the garden." cr ;

: garden-desc
    ." Wonderful, wonderful grass!" cr
    ." The hallway is back SOUTH." cr
    ." A gap in the fence leads NORTH to the road." cr ;

: road-desc
    ." A quiet country road." cr
    ." The garden is back SOUTH." cr
    ." An old WELL stands EAST in a misty field." cr ;

: well-desc
    ." A deep, dark, scary well." cr
    ." You can hear faint whimpering far below." cr
    ." The road is back to the WEST." cr ;


\ Rooms
\ ─────
\ Each room is 8 bytes of exits — four cells, one per direction, all
\ initialised to "blocked" — followed by the xt of its description.
\ init-exits will rewrite the exit cells at run time; the description
\ stays put.  Listing every room in the `rooms` array gives a single
\ handle for code that wants to iterate over all of them.

0
8 -- .exits
2 -- .description
STRUCT /room

create kitchen   -1 , -1 , -1 , -1 ,   ' kitchen-desc ,
create hallway   -1 , -1 , -1 , -1 ,   ' hallway-desc ,
create garden    -1 , -1 , -1 , -1 ,   ' garden-desc ,
create road      -1 , -1 , -1 , -1 ,   ' road-desc ,
create well      -1 , -1 , -1 , -1 ,   ' well-desc ,

w: rooms   ' kitchen , ' hallway , ' garden , ' road , ' well , ;


\ Exits: basics
\ ─────────────
\ An exit cell holds either a target room's address or -1 ("blocked").
\ exit-cell does the offset arithmetic; the rest is a thin layer over
\ @, !, and =.

: exit-cell      ( room dir -- addr )    2 *  swap .exits +  + ;
: exit-of        ( room dir -- target )  exit-cell @ ;
: blocked?       ( target -- flag )      -1 = ;
: connect        ( target room dir -- )  exit-cell ! ;


\ Exits: bidirectional connection
\ ───────────────────────────────
\ Adventure-game corridors should be walkable both ways: if the
\ kitchen's north exit goes to the hallway, the hallway's south exit
\ had better go back.  connect-pair wires both directions in one call,
\ using opposite-dir for the return trip.

: connect-pair   ( a b dir -- )
    >r  2dup swap  r@           connect
    r>           opposite-dir   connect ;


\ Exits: clearing a room
\ ──────────────────────
\ -1 is the "blocked" sentinel, but `fill` writes one byte at a time
\ and exits are 16-bit cells.  We want every byte to be 255, which is
\ (-1 & 0xFF) and sign-extends back to -1 when read as a cell.

: clear-exits    ( room -- )    .exits +  8 255 fill ;


\ Exits: the corridor table
\ ─────────────────────────
\ One row across these three parallel arrays describes one bidirectional
\ corridor.  Cell-arrays for "from" and "to" hold room addresses; a
\ byte-array for "dir" holds the four-valued direction.  install-edges
\ walks the rows in lockstep and lets connect-pair fill in each pair.
\ Adding a passage is one entry in each array.

w: edge-from   ' kitchen , ' hallway , ' garden  , ' road    , ;
w: edge-to     ' hallway , ' garden  , ' road    , ' well    , ;
c: edge-dir    dir-n c, dir-n c, dir-n c, dir-e c, ;

: install-edge   ( i -- )
    dup    edge-from swap a-word@
    over   edge-to   swap a-word@
    rot    edge-dir  swap a-byte@
    connect-pair ;

: install-edges
    edge-from a-count 0 do  i install-edge  loop ;


\ Exits: assembly
\ ───────────────
\ Reset every room's exits to "blocked", then wire each corridor.  The
\ clear pass matters because reset-game runs more than once — the
\ exits compiled into the room records are the initial values, not a
\ permanent default.

: init-exits
    rooms ['] clear-exits for-each-word
    install-edges ;


\ Player and item state
\ ─────────────────────
\ Two mutable variables hold the entire dynamic game state.  here-room
\ is a room address.  item-loc is a 3-cell array indexed by item id;
\ each slot holds a room address, `carried`, or `nowhere`.  Storing the
\ location *on the item* (rather than items on rooms) makes "where is
\ X?" O(1) and makes "X exists in two places" structurally impossible.

variable here-room

w: item-loc    nowhere , nowhere , nowhere , ;
w: item-homes  ' kitchen , ' garden , ' well , ;

: item-room@     ( id -- where )    item-loc swap  a-word@ ;
: item-room!     ( where id -- )    item-loc swap  a-word! ;


\ Placing items at the start of a game
\ ────────────────────────────────────
\ place-items wants to copy item-homes into item-loc, slot for slot.
\ The natural fit is `item-loc ['] copy-from-homes map-word`, but
\ map-word's xt sees ( v -- v' ) — the current value, not the index.
\ So we thread the index through __place-i ourselves.  As a bonus,
\ map-word overwrites every slot, so no separate clear pass is needed.

variable __place-i

: home-of-next   ( v -- v' )
    drop  item-homes __place-i @ a-word@
    1 __place-i +! ;

: place-items
    0 __place-i !
    item-loc ['] home-of-next map-word ;


\ Item queries
\ ────────────
\ Thin wrappers over item-room@.  `here?` and `carrying?` are stated in
\ terms of `item-room@ <something> =` rather than going through
\ in-room? so the simpler intent stays readable at the call site.

: in-room?       ( id room -- flag )   swap item-room@ = ;
: room-has?      ( id room -- flag )   in-room? ;
: carrying?      ( id -- flag )        item-room@ carried = ;
: have-stick?    ( -- flag )           stick carrying? ;
: here?          ( id -- flag )        item-room@ here-room @ = ;


\ Item search
\ ───────────
\ pick-at finds the first item id whose location matches `where`, or
\ -1 if none.  Same side-channel pattern as place-items:
\ index-of?-word's predicate sees only the array value, so the search
\ target rides in __pick-target.

variable __pick-target

: at-pick-target?   ( where -- flag )   __pick-target @ = ;

: pick-at        ( where -- id|-1 )
    __pick-target !
    item-loc ['] at-pick-target?  index-of?-word
    if exit then
    drop -1 ;
