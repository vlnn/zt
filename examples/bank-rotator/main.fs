\ examples/bank-rotator/main.fs
\
\ M5 acceptance demo for 128K support.
\
\ Seeds six of the 128K banks with distinctive attribute bytes, then in the
\ main loop pages through them and copies each bank's first byte into the
\ corresponding column of the Spectrum attribute area — producing a visible
\ strip of stripes that proves the paging logic is doing real work.
\
\ Bank layout:
\   bank 0, 1, 3, 4, 6, 7 — each seeded with a different attribute byte.
\   bank 2                — always mapped at $8000; holds code and stacks.
\   bank 5                — always mapped at $4000; holds the screen.
\
\ Runs correctly on a real 128K Spectrum or on an emulator in 128K mode.
\ On a 48K machine, `128k?` returns false and the program halts with a red
\ border as a visible failure signal.

: ensure-128k  ( -- )
    128k? 0= if 2 border begin again then ;

: seed-bank  ( attr-byte bank -- )
    bank! $C000 c! ;

: install-banks  ( -- )
    $46 0 seed-bank      \ bright white ink on bright red paper
    $4A 1 seed-bank      \ bright cyan ink on bright red paper
    $52 3 seed-bank      \ bright red ink on bright green paper
    $61 4 seed-bank      \ black ink on bright blue paper
    $46 6 seed-bank
    $4A 7 seed-bank ;

: show-bank-at-col  ( bank col -- )
    swap bank!           ( col )
    $C000 c@             ( col attr-byte )
    swap $5800 + c! ;    \ attrs[col] = attr-byte

: cycle  ( -- )
    0 0 show-bank-at-col
    1 1 show-bank-at-col
    3 2 show-bank-at-col
    4 3 show-bank-at-col
    6 4 show-bank-at-col
    7 5 show-bank-at-col ;

: main
    ensure-128k
    7 0 cls
    install-banks
    begin cycle again ;
