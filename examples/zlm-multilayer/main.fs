\ examples/zlm-multilayer/main.fs — z80ai port, tier (B): multi-layer forward pass.
\
\ A 4-layer MLP (8 → 8 → 4 → 3) with 2-bit signed weights, ReLU between hidden
\ layers and no activation on the final layer. Argmax over the 3 logits gives a
\ predicted class index, printed as `predicted: N`.
\
\ Weights and inputs come from gen_weights.py (seed=42). Re-running the generator
\ regenerates weights.fs; the test in tests/test_examples_zlm_multilayer.py
\ recomputes the expected argmax in Python and asserts it matches the screen.
\
\ Build:  uv run python -m zt.cli build examples/zlm-multilayer/main.fs -o build/zlm-multilayer.sna
\ Run:    open build/zlm-multilayer.sna in any Spectrum 48K emulator.

require weights.fs

create acts1   16 allot
create acts2    8 allot
create acts3    6 allot

variable lp-in
variable lp-aptr
variable lp-wptr
variable lp-opt
variable lp-rowbytes

variable am-best-idx
variable am-best-val

: relu       ( n -- n' )    dup 0< if drop 0 then ;
: relu!      ( addr -- )    dup @ relu swap ! ;

: nth-cell   ( base i -- addr )    2 * + ;

: relu-cells ( addr count -- )
    0 do  dup i nth-cell relu!  loop drop ;

: zero-cell  ( addr -- )    0 swap ! ;

: bytes-per-row ( in-count -- bytes )    2 rshift ;

: layer-pass ( wptr aptr in-count opt-base out-count -- )
    >r
    lp-opt !
    dup lp-in !
    bytes-per-row lp-rowbytes !
    lp-aptr !
    lp-wptr !
    r> 0 do
        lp-wptr @
        lp-aptr @
        lp-in   @
        lp-opt  @  dup zero-cell
        2bit-dot+!
        lp-wptr @  lp-rowbytes @  +  lp-wptr !
        lp-opt  @                2 +  lp-opt  !
    loop ;

: argmax ( base count -- idx )
    >r
    dup @ am-best-val !
    0 am-best-idx !
    r> 1 do
        dup i nth-cell @
        dup am-best-val @ > if
            am-best-val !
            i am-best-idx !
        else
            drop
        then
    loop drop
    am-best-idx @ ;

: forward
    weights1  acts0  8  acts1  8  layer-pass
    acts1     8                  relu-cells
    weights2  acts1  8  acts2  4  layer-pass
    acts2     4                  relu-cells
    weights3  acts2  4  acts3  3  layer-pass ;

: print-logits
    0 4 at-xy ." logits: "
    3 0 do  acts3 i nth-cell @ .  loop ;

: print-prediction ( idx -- )
    0 5 at-xy
    ." predicted: " . ;

: print-banner
    0 0 at-xy  ." zlm-multilayer demo (8x8x4x3)" cr
    0 1 at-xy  ." seed 42, 2-bit signed weights" ;

: main
    7 0 cls
    print-banner
    forward
    print-logits
    acts3 3 argmax print-prediction
    begin again ;
