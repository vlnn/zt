require core.fs
require world.fs

variable game-over

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

: describe-room
    here-room @
    case
        kitchen of kitchen-desc endof
        hallway of hallway-desc endof
        garden  of garden-desc  endof
        road    of road-desc    endof
        well    of well-desc    endof
        well-desc
    endcase ;

: bone-name    ." bone" ;
: stick-name   ." stick" ;
: ball-name    ." red ball" ;

create item-printers
    ' bone-name , ' stick-name , ' ball-name ,

: print-item-name  ( id -- )  2 *  item-printers + @ execute ;

: announce-here  ( id -- )
    ." There is a " print-item-name ." here." cr ;

: list-items-here
    n-items 0 do
        i here? if i announce-here then
    loop ;

: list-inventory
    ." You are carrying: "
    0
    n-items 0 do
        i carrying? if
            i print-item-name space
            1+
        then
    loop
    0= if ." nothing." cr else cr then ;

: look-here
    describe-room
    list-items-here ;

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

: show-msg
    last-msg @
    case
        msg-welcome      of print-welcome   endof
        msg-no-exit      of print-no-exit   endof
        msg-too-scary    of print-too-scary endof
        msg-bravely-east of print-brave     endof
        msg-took         of print-took      endof
        msg-dropped      of print-dropped   endof
        msg-nothing-here of print-nothing   endof
        msg-jaws-empty   of print-empty     endof
        msg-bark         of print-bark      endof
        msg-help         of print-help      endof
        msg-unknown      of print-unknown   endof
        msg-celebrate    of print-celebrate endof
    endcase ;

: maybe-inventory
    show-inv? @ if 0 show-inv? ! list-inventory then ;

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

: pick-here     ( -- id|-1 )
    n-items 0 do
        i here? if i unloop exit then
    loop -1 ;

: pick-carried  ( -- id|-1 )
    n-items 0 do
        i carrying? if i unloop exit then
    loop -1 ;

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

: do-bark       1 50 beep msg-bark last-msg ! ;
: do-look       msg-quiet last-msg ! ;
: do-help       msg-help last-msg ! ;
: do-quit       1 game-over ! ;
: do-inventory  1 show-inv? ! msg-quiet last-msg ! ;
: do-empty      msg-quiet last-msg ! ;
: do-unknown    msg-unknown last-msg ! ;

: dispatch      ( c -- )
    case
        0     of do-empty     endof
        key-n of do-north     endof
        key-s of do-south     endof
        key-e of do-east      endof
        key-w of do-west      endof
        key-l of do-look      endof
        key-t of do-take      endof
        key-g of do-take      endof
        key-d of do-drop      endof
        key-i of do-inventory endof
        key-b of do-bark      endof
        key-h of do-help      endof
        key-? of do-help      endof
        key-q of do-quit      endof
        do-unknown
    endcase ;

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

: won?          ball item-room@ kitchen = ;

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
