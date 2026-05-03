require core.fs

\ Items live in a bitmap byte per room: bit `id` set iff item `id` is here.
\ Carried items live in carried-mask, *not* in any room's .items.

0 constant bone
1 constant stick
2 constant ball

-2 constant carried           \ sentinel returned by item-room@ for items in jaws

\ Direction = cell index within a room's .exits array.

0 constant dir-n
1 constant dir-s
2 constant dir-e
3 constant dir-w

\ Description words.  Defined before rooms so each room's .description
\ field can be initialised at compile time with `' word ,`.

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

\ A room owns its outgoing exits, the items currently in it, and the xt of
\ its description.  11 bytes per room.

0
8 -- .exits                   \ four cells: target room addr per direction (-1 = blocked)
1 -- .items                   \ presence bitmap, one bit per item id
2 -- .description             \ xt of the description word
STRUCT /room

\ Each room is laid out by hand so .description can be a compile-time xt.
\ Exits start blocked (-1); items start empty; runtime init-exits and
\ place-items wire up the actual world.

create kitchen
    -1 , -1 , -1 , -1 ,   0 c,   ' kitchen-desc ,
create hallway
    -1 , -1 , -1 , -1 ,   0 c,   ' hallway-desc ,
create garden
    -1 , -1 , -1 , -1 ,   0 c,   ' garden-desc ,
create road
    -1 , -1 , -1 , -1 ,   0 c,   ' road-desc ,
create well
    -1 , -1 , -1 , -1 ,   0 c,   ' well-desc ,

\ Sentinel-terminated array of all rooms.  The 0 cell ends the list so
\ each-room can walk it without a count.

create rooms-list
    ' kitchen , ' hallway , ' garden , ' road , ' well ,  0 ,

: each-room      ( xt -- )
    >r rooms-list
    begin dup @ dup while
        r@ execute  2 +
    repeat 2drop r> drop ;

\ Exits ─────────────────────────────────────────────────────────────────────

: exit-cell      ( room dir -- addr )  2 * .exits + + ;
: exit-of        ( room dir -- target ) exit-cell @ ;
: blocked?       ( target -- flag )    -1 = ;
: connect        ( target room dir -- ) exit-cell ! ;

: clear-exits    ( room -- )           .exits + 8 255 fill ;
' clear-exits    constant xt-clear-exits

: clear-all-exits   xt-clear-exits each-room ;

: init-exits
    clear-all-exits
    hallway kitchen dir-n connect
    kitchen hallway dir-s connect
    garden  hallway dir-n connect
    hallway garden  dir-s connect
    road    garden  dir-n connect
    garden  road    dir-s connect
    well    road    dir-e connect
    road    well    dir-w connect ;

\ Items ─────────────────────────────────────────────────────────────────────

variable here-room            \ holds a room address, not an index
variable carried-mask         \ byte bitmap of items currently held

: item-bit       ( id -- mask )        1 swap lshift ;

\ Walk the set bits of `bitmap`, calling xt with each bit's position.
\ Item ids are bit positions, so this is "for each item in the set".

: each-bit       ( bitmap xt -- )
    >r 0
    begin over while
        over 1 and if dup r@ execute then
        swap 1 rshift swap 1+
    repeat 2drop r> drop ;

\ Lowest set bit position, or -1 if none — i.e. "first item in the set".

: first-bit      ( bitmap -- pos|-1 )
    dup 0= if drop -1 exit then
    0
    begin over 1 and 0= while
        swap 1 rshift swap 1+
    repeat nip ;

: room-items@    ( room -- bitmap )    .items >c@ ;
: room-items!    ( bitmap room -- )    .items >c! ;

: room-has?      ( id room -- flag )   room-items@ swap item-bit and 0= invert ;

: add-to-room    ( id room -- )
    dup room-items@ rot item-bit or  swap room-items! ;

: remove-from-room ( id room -- )
    dup room-items@ rot item-bit invert and  swap room-items! ;

: clear-items    ( room -- )           0 swap room-items! ;
' clear-items    constant xt-clear-items

: clear-all-items   xt-clear-items each-room  0 carried-mask c! ;

: here?          ( id -- flag )        here-room @ room-has? ;
: carrying?      ( id -- flag )        carried-mask c@ swap item-bit and 0= invert ;
: have-stick?    ( -- flag )           stick carrying? ;

\ Public location API.  Items only ever live in exactly one place — a room
\ or the player's jaws — so item-room@ is a carried? short-circuit followed
\ by a walk over rooms-list looking for a room whose .items has the bit.

: item-room@     ( id -- where )
    dup carrying? if drop carried exit then
    >r rooms-list
    begin dup @ dup while
        r@ over room-has? if  nip r> drop exit  then
        drop 2 +
    repeat
    2drop r> drop -1 ;

: pickup-item    ( id -- )
    dup item-bit  carried-mask c@ or  carried-mask c! ;

: drop-from-jaws ( id -- )
    item-bit invert  carried-mask c@ and  carried-mask c! ;

: forget-item    ( id -- )
    dup item-room@                       ( id where )
    dup carried = if drop drop-from-jaws exit then
    dup -1      = if 2drop exit then
    remove-from-room ;

: item-room!     ( where id -- )
    dup forget-item
    over carried = if
        nip pickup-item
    else
        swap add-to-room
    then ;

: place-items
    clear-all-items
    kitchen bone  item-room!
    garden  stick item-room!
    well    ball  item-room! ;
