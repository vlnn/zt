\ The turn loop: input handling, command dispatch, message playback, and
\ the screen-clearing render cycle.  The world model lives in world.fs;
\ this file is everything that touches it from outside.

require core.fs
require array-hof.fs
require world.fs

variable game-over


\ Showing the world
\ ─────────────────
\ Each item id has a printer xt at the same index in `item-printers`,
\ matching the convention from world.fs that ids index every per-item
\ array (item-loc, item-homes, item-printers).  list-items-here and
\ list-inventory walk item-loc by id, not by HOF — `here?` and
\ `carrying?` need the id, which `for-each-word`'s `( v -- )` xt
\ doesn't provide.

: describe-room  here-room @ .description >@ execute ;

: bone-name    ." bone" ;
: stick-name   ." stick" ;
: ball-name    ." red ball" ;

w: item-printers   ' bone-name , ' stick-name , ' ball-name , ;

: print-item-name   ( id -- )   item-printers swap a-word@ execute ;

: announce-here     ( id -- )   ." There is a " print-item-name ." here." cr ;
: print-with-space  ( id -- )   print-item-name space ;

: list-items-here
    item-loc a-count 0 do
        i here? if i announce-here then
    loop ;


\ Inventory
\ ─────────
\ One pass over item-loc, with a flag tracking whether anything was
\ carried so the trailing "nothing." is only printed when the loop
\ saw nothing.  The alternative — `count-if-word` to pre-check —
\ would walk the array twice.

variable any-carried?

: list-inventory
    ." You are carrying: "
    0 any-carried? !
    item-loc a-count 0 do
        i carrying? if  i print-with-space  1 any-carried? !  then
    loop
    any-carried? @ 0= if ." nothing." then
    cr ;

: look-here   describe-room  list-items-here ;


\ Reading the player's command
\ ────────────────────────────
\ Line-buffered input: read-line collects bytes into cmd-buf until the
\ user presses Enter, then first-char strips leading spaces and returns
\ the lowercased first byte for dispatch to chew on.  `lower` is
\ hand-rolled because the stdlib doesn't ship it yet.  read-key
\ debounces by waiting for both press and release — without that, the
\ Spectrum's auto-repeat would deliver duplicate keystrokes.

create cmd-buf 32 allot
32 constant cmd-max
variable cmd-len

: lower         ( c -- c' )
    dup 65 < if exit then
    dup 90 > if exit then
    32 + ;

: wait-press    begin key? until ;
: wait-release  begin key? 0= until ;
: read-key      wait-press key wait-release ;

: input-append  ( c -- )
    cmd-len @ cmd-max = if drop exit then
    cmd-buf cmd-len @ + c!
    1 cmd-len +! ;

: read-line
    0 cmd-len !
    begin
        read-key dup 13 <>
    while
        dup emit
        input-append
    repeat
    drop ;

: skip-spaces   ( -- addr len )
    cmd-buf cmd-len @
    begin dup 0 > while
        over c@ 32 <> if exit then
        1 - swap 1+ swap
    repeat ;

: first-char    ( -- c|0 )
    skip-spaces dup 0= if 2drop 0 exit then
    drop c@ lower ;


\ Key codes
\ ─────────
\ Every verb collapses to its first letter, sometimes with a synonym
\ (G alongside T for take, ? alongside H for help).  Sticking to
\ first-letter dispatch sidesteps the COMPARE / upper-case gaps in the
\ current Forth (see FORTH-ROADMAP.md) and keeps the dispatcher table
\ to a single byte per verb.

110 constant key-n
115 constant key-s
101 constant key-e
119 constant key-w
108 constant key-l
116 constant key-t
103 constant key-g
100 constant key-d
105 constant key-i
98  constant key-b
104 constant key-h
63  constant key-?
113 constant key-q


\ Deferred messages
\ ─────────────────
\ Every command sets `last-msg` instead of printing.  render then runs
\ `show-msg` *after* clearing the screen, so the player sees both the
\ result of their previous action and the current room together — the
\ thing that would otherwise scroll off above the cursor sticks around
\ for one more frame.  msg-quiet is a no-op printer for commands whose
\ effect is visible elsewhere (look, inventory, blank input).

variable last-msg
variable last-item
variable show-inv?

0  constant msg-welcome
1  constant msg-no-exit
2  constant msg-too-scary
3  constant msg-bravely-east
4  constant msg-took
5  constant msg-dropped
6  constant msg-nothing-here
7  constant msg-jaws-empty
8  constant msg-bark
9  constant msg-help
10 constant msg-unknown
11 constant msg-quiet
12 constant msg-celebrate

: print-took       ." You take the "  last-item @ print-item-name ." ." cr ;
: print-dropped    ." You drop the "  last-item @ print-item-name ." ." cr ;
: print-welcome    ." Time for a walk!" cr ;
: print-no-exit    ." You bonk your snoot. No way that direction." cr ;
: print-too-scary  ." TOO SCARY! You whimper and pad back to safety." cr ;
: print-brave      ." Holding the stick high, you brave the well." cr ;
: print-nothing    ." There is nothing here to take." cr ;
: print-empty      ." Your jaws are empty." cr ;
: print-bark       ." WOOF!" cr ;
: print-unknown    ." Awoo? You twirl in confusion." cr ;
: print-quiet      ;

: print-celebrate
    cr
    ." *** GOOD CORGI! ***" cr
    ." You brought the ball home." cr
    ." The puppy upstairs cheers!" cr ;

: print-help
    ." Type a command and press ENTER." cr
    ." First letter is enough:" cr
    ."   N S E W   move (north, south, east, west)" cr
    ."   LOOK      describe surroundings" cr
    ."   TAKE      grab the thing here" cr
    ."   DROP      drop something" cr
    ."   INV       inventory" cr
    ."   BARK      WOOF!" cr
    ."   HELP      this help" cr
    ."   QUIT      stop the game" cr ;

w: msg-printers
    ' print-welcome     ,
    ' print-no-exit     ,
    ' print-too-scary   ,
    ' print-brave       ,
    ' print-took        ,
    ' print-dropped     ,
    ' print-nothing     ,
    ' print-empty       ,
    ' print-bark        ,
    ' print-help        ,
    ' print-unknown     ,
    ' print-quiet       ,
    ' print-celebrate   ,
;

: show-msg   last-msg @  msg-printers swap  a-word@ execute ;

: maybe-inventory
    show-inv? @ if 0 show-inv? ! list-inventory then ;


\ Movement
\ ────────
\ try-go is the general case: look up the exit, refuse if blocked,
\ otherwise move.  do-east is special-cased for the road→well corridor
\ because it requires the stick.  Putting the stick check inside
\ try-go would couple a movement primitive to one specific corridor;
\ instead, do-east handles the location-specific logic and falls
\ through to try-go everywhere else.

: try-go        ( dir -- )
    here-room @ swap exit-of
    dup blocked? if drop msg-no-exit last-msg ! exit then
    here-room !
    msg-quiet last-msg ! ;

: try-east-from-road
    have-stick? if
        well here-room !
        msg-bravely-east last-msg !
    else
        msg-too-scary last-msg !
    then ;

: do-east
    here-room @ road = if try-east-from-road exit then
    dir-e try-go ;

: do-north      dir-n try-go ;
: do-south      dir-s try-go ;
: do-west       dir-w try-go ;


\ Take and drop
\ ─────────────
\ pick-here finds the first item in the current room; pick-carried
\ does the same for items in the player's jaws.  Both are one-liners
\ over pick-at, which is the single search primitive in world.fs.
\ The dup/-1 check covers the "no items found" case.

: pick-here     ( -- id|-1 )   here-room @  pick-at ;
: pick-carried  ( -- id|-1 )   carried      pick-at ;

: do-take
    pick-here
    dup -1 = if drop msg-nothing-here last-msg ! exit then
    dup last-item !
    dup carried swap item-room!
    drop
    msg-took last-msg ! ;

: do-drop
    pick-carried
    dup -1 = if drop msg-jaws-empty last-msg ! exit then
    dup last-item !
    here-room @ over item-room!
    drop
    msg-dropped last-msg ! ;


\ Other commands
\ ──────────────
\ Each collapses to setting last-msg, sometimes plus one flag
\ (show-inv?, game-over).  None move the player or change item
\ locations; that's what makes them safe to leave as one-liners.

: do-bark       1 50 beep msg-bark last-msg ! ;
: do-look       msg-quiet last-msg ! ;
: do-help       msg-help last-msg ! ;
: do-quit       1 game-over ! ;
: do-inventory  1 show-inv? !  msg-quiet last-msg ! ;
: do-empty      msg-quiet last-msg ! ;
: do-unknown    msg-unknown last-msg ! ;


\ The dispatcher
\ ──────────────
\ Two parallel arrays: cmd-keys[i] is the lowercased first letter that
\ triggers cmd-actions[i].  Adding a verb is one byte plus one xt;
\ adding a synonym means repeating the action xt at the right index
\ (T and G both fire do-take; H and ? both fire do-help).  Slot 0
\ pairs the byte 0 with do-empty so blank input — for which first-char
\ returns 0 — dispatches without a special case.  __cmd-key threads
\ the key byte through index-of?-byte's predicate, which only sees
\ the array value.

c: cmd-keys
    0      c,
    key-n  c, key-s c, key-e c, key-w c,
    key-l  c, key-t c, key-g c,
    key-d  c,
    key-i  c,
    key-b  c,
    key-h  c, key-?  c,
    key-q  c,
;

w: cmd-actions
    ' do-empty       ,
    ' do-north , ' do-south , ' do-east , ' do-west ,
    ' do-look  , ' do-take  , ' do-take  ,
    ' do-drop  ,
    ' do-inventory   ,
    ' do-bark        ,
    ' do-help  , ' do-help  ,
    ' do-quit        ,
;

variable __cmd-key

: __cmd-match?   ( v -- flag )   __cmd-key @ = ;

: dispatch      ( c -- )
    __cmd-key !
    cmd-keys ['] __cmd-match?  index-of?-byte
    if    cmd-actions swap a-word@ execute
    else  drop do-unknown
    then ;


\ The render cycle
\ ────────────────
\ Frame layout: clear, replay the previous turn's message, optionally
\ list the inventory (one-shot — show-inv? clears itself), blank line,
\ describe the current room, blank line, prompt.  final-render is the
\ same up through show-msg and ends with a "press any key" wait so
\ the celebration message stays on screen.

: prompt        ." > " ;

: render
    7 0 cls
    show-msg
    maybe-inventory
    cr
    look-here
    cr
    prompt ;

: final-render
    7 0 cls
    show-msg
    cr
    ." Press any key." cr
    read-key drop ;

: intro
    7 0 cls
    ." CORGI ADVENTURES" cr cr
    ." A small dog dropped their ball into the spooky" cr
    ." old well. Be a brave good corgi: bring it home." cr cr
    ." Press any key to start..." cr
    read-key drop ;


\ The game loop
\ ─────────────
\ reset-game restores everything that can change during play, in case
\ the loop is ever entered more than once.  A turn is render →
\ read-line → dispatch — display the result of last turn first, then
\ collect input, then act.  won? checks for the ball back in the
\ kitchen; celebrate flips both the win message and the exit flag in
\ one place.

: reset-game
    0 game-over !
    0 show-inv? !
    msg-welcome last-msg !
    kitchen here-room !
    init-exits
    place-items ;

: turn
    render
    read-line
    cr
    first-char dispatch ;

: won?          ball item-room@  kitchen = ;

: celebrate     msg-celebrate last-msg !  1 game-over ! ;

: run-corgi
    intro
    reset-game
    begin
        turn
        won? if celebrate then
        game-over @
    until
    final-render ;
