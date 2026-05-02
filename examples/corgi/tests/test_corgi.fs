include test-lib.fs
require ../app/game.fs

: test-start-room-is-kitchen
    reset-game  here-room @  kitchen assert-eq ;

: test-bone-starts-in-kitchen
    reset-game  bone item-room@  kitchen assert-eq ;

: test-stick-starts-in-garden
    reset-game  stick item-room@  garden assert-eq ;

: test-ball-starts-in-well
    reset-game  ball item-room@  well assert-eq ;

: test-init-exits-wires-kitchen-north
    reset-game  kitchen dir-n exit-of  hallway assert-eq ;

: test-init-exits-wires-kitchen-east-blocked
    reset-game  kitchen dir-e exit-of  -1 assert-eq ;

: test-do-north-from-kitchen
    reset-game  do-north  here-room @  hallway assert-eq ;

: test-do-east-from-kitchen-blocked-and-flagged
    reset-game  do-east  last-msg @  msg-no-exit assert-eq ;

: test-walk-to-road
    reset-game  do-north do-north do-north
    here-room @  road assert-eq ;

: test-east-from-road-without-stick-stays-on-road
    reset-game  do-north do-north do-north  do-east
    here-room @  road assert-eq ;

: test-east-from-road-without-stick-flags-too-scary
    reset-game  do-north do-north do-north  do-east
    last-msg @  msg-too-scary assert-eq ;

: test-east-from-road-with-stick-reaches-well
    reset-game  do-north do-north
    do-take  do-north  do-east
    here-room @  well assert-eq ;

: test-do-take-bone-puts-it-in-jaws
    reset-game  do-take
    bone item-room@  carried assert-eq ;

: test-do-take-bone-flags-took
    reset-game  do-take
    last-msg @  msg-took assert-eq ;

: test-do-drop-puts-bone-in-current-room
    reset-game  do-take  do-drop
    bone item-room@  kitchen assert-eq ;

: test-do-drop-flags-dropped
    reset-game  do-take  do-drop
    last-msg @  msg-dropped assert-eq ;

: test-do-take-empty-flags-nothing-here
    reset-game  do-take  do-take
    last-msg @  msg-nothing-here assert-eq ;

: test-do-drop-empty-flags-jaws-empty
    reset-game  do-drop
    last-msg @  msg-jaws-empty assert-eq ;

: test-not-won-at-start
    reset-game  won?  assert-false ;

: test-not-won-while-carrying-ball-in-kitchen
    reset-game  carried ball item-room!
    won?  assert-false ;

: test-won-when-ball-rests-in-kitchen
    reset-game  kitchen ball item-room!
    won?  assert-true ;

: test-blocked-flag-on-minus-one
    -1 blocked?  assert-true ;

: test-blocked-flag-false-on-real-room
    kitchen blocked?  assert-false ;

: test-lower-uppercase-becomes-lower
    65 lower  97 assert-eq ;

: test-lower-lowercase-passes-through
    113 lower  113 assert-eq ;

: test-lower-non-letter-passes-through
    63 lower  63 assert-eq ;

: test-do-quit-sets-game-over
    reset-game  do-quit
    game-over @  1 assert-eq ;

: test-do-inventory-sets-show-inv-flag
    reset-game  do-inventory
    show-inv? @  1 assert-eq ;

: test-do-help-flags-help
    reset-game  do-help
    last-msg @  msg-help assert-eq ;

: test-do-bark-flags-bark
    reset-game  do-bark
    last-msg @  msg-bark assert-eq ;

: test-dispatch-h-fires-help
    reset-game  104 dispatch
    last-msg @  msg-help assert-eq ;

: test-dispatch-question-mark-fires-help
    reset-game  63 dispatch
    last-msg @  msg-help assert-eq ;

: test-dispatch-empty-fires-quiet
    reset-game  0 dispatch
    last-msg @  msg-quiet assert-eq ;

: test-dispatch-unknown-letter-flags-unknown
    reset-game  122 dispatch
    last-msg @  msg-unknown assert-eq ;
