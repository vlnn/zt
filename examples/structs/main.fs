\ Structs demo — exercise every kind of struct field access introduced in
\ Phase 5 of the compiler:
\
\   - STRUCT / record / -- offset directives
\   - Static-instance fusion:    hero .hp >c!     (named record + known offset)
\   - Dynamic-instance fusion:   .hp >c@          (instance from stack, in
\                                                  generic accessor colons)
\   - Inheritance via stacked STRUCTs
\
\ The example simulates one round of a tiny RPG: three actors take turns
\ damaging each other, then the program leaves their final HP values on the
\ data stack so a test can verify them.
\
\ Build:  zt build examples/structs/main.fs -o build/structs.sna
\                                          --map build/structs.map

require app/menagerie.fs

: main
    setup-actors
    fight-one-round
    print-results
    \ Leave [troll-hp, goblin-hp, hero-hp] on the data stack for the test.
    troll  actor-hp
    goblin actor-hp
    hero   actor-hp
    halt ;
