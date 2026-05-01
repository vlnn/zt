\ Demo for asm-primitives.fs — exercises each ::: word with visible output.
\
\ Build:
\   uv run python -m zt.cli build examples/asm-primitives-demo.fs \
\                                 -o build/asm-primitives.sna \
\                                 --map build/asm-primitives.map
\
\ Run the resulting .sna in any Spectrum emulator (Fuse, ZEsarUX, etc.).
\
\ Expected screen output:
\   1002          \ 1000 cell+
\   7 7           \ 7 ?dup
\   0             \ 0 ?dup
\   A             \ 64 1c+! emitted as char
\   1             \ 5 bit0?
\   0             \ 4 bit0?
\ Plus the entire attribute area painted bright white (the fill-byte demo).

require asm-primitives.fs

variable demo-cell

: demo-cell-arith  ( -- )    1000 cell+ . cr ;
: demo-?dup-nz     ( -- )    7 ?dup . . cr ;
: demo-?dup-zero   ( -- )    0 ?dup . cr ;
: demo-byte-bump   ( -- )    64 demo-cell c!  demo-cell 1c+!  demo-cell c@ emit cr ;
: demo-fill        ( -- )    22528 768 56 fill-byte ;
: demo-bit0        ( -- )    5 bit0? . cr  4 bit0? . cr ;

: main
    0 7 cls
    demo-cell-arith
    demo-?dup-nz
    demo-?dup-zero
    demo-byte-bump
    demo-fill
    demo-bit0 ;
