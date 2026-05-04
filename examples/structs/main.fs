\ Demo for every kind of struct field access introduced in Phase 5 of
\ the compiler: STRUCT / record / -- offset directives, static-instance
\ fusion (named record + known offset, e.g. `hero .hp >c!`), dynamic-
\ instance fusion (instance from stack, inside generic accessor colons),
\ and inheritance via stacked STRUCTs.  The example runs five rounds of
\ a tiny RPG: three actors take turns damaging each other each round,
\ then leaves their final HP values on the data stack so a test can
\ verify them.
\
\ Build:  zt build examples/structs/main.fs -o build/structs.sna
\                                          --map build/structs.map

require app/menagerie.fs
require ../stdlib/input.fs

: tick
    fight-one-round
    print-results ;

: main
    setup-actors
    [TIMES] 5 tick
    ." GAME OVER"
    troll  actor-hp
    goblin actor-hp
    hero   actor-hp
    halt ;
