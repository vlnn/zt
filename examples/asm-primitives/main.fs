\ Visible-output demo for asm-primitives.fs — exercises each `:::` word
\ with a printed result, plus a screen-fill at the end.  Build, run in
\ any Spectrum emulator (Fuse, ZEsarUX), and the screen will show:
\
\     1002          \ 1000 cell+
\     7 7           \ 7 ?dup
\     0             \ 0 ?dup
\     A             \ 64 1c+! emitted as a char
\     1             \ 5 bit0?
\     0             \ 4 bit0?
\
\ followed by the entire attribute area painted bright white — that's
\ the fill-byte demo writing 768 copies of attribute 56 to $5800.
\
\ Build:
\   uv run python -m zt.cli build examples/asm-primitives-demo.fs \
\       -o build/asm-primitives.sna --map build/asm-primitives.map

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
