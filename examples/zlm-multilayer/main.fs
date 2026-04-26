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

\ rectified linear: clamp negative inputs to zero
: relu       ( n -- n' )    dup 0< if drop 0 then ;
\ apply ReLU to the cell at addr in place
: relu!      ( addr -- )    dup @ relu swap ! ;

\ address of the i-th 16-bit cell of base
: nth-cell   ( base i -- addr )    2 * + ;

\ apply ReLU element-wise to count cells starting at addr
: relu-cells ( addr count -- )
    0 do  dup i nth-cell relu!  loop drop ;

\ store zero into the cell at addr
: zero-cell  ( addr -- )    0 swap ! ;

\ packed weight-matrix row size in bytes for a layer with in-count inputs
: bytes-per-row ( in-count -- bytes )    2 rshift ;

\ run one fully-connected layer: out = W x in (2-bit packed weights)
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

\ index of the largest cell in a count-cell vector at base
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

\ forward pass through all three layers, leaving logits in acts3
: forward
    weights1  acts0  8  acts1  8  layer-pass
    acts1     8                  relu-cells
    weights2  acts1  8  acts2  4  layer-pass
    acts2     4                  relu-cells
    weights3  acts2  4  acts3  3  layer-pass ;

\ print the three output logits at row 4
: print-logits
    0 4 at-xy ." logits: "
    3 0 do  acts3 i nth-cell @ .  loop ;

\ print "predicted: N" at row 5
: print-prediction ( idx -- )
    0 5 at-xy
    ." predicted: " . ;

\ print the demo banner at the top of the screen
: print-banner
    0 0 at-xy  ." zlm-multilayer demo (8x8x4x3)" cr
    0 1 at-xy  ." seed 42, 2-bit signed weights" ;

\ entry point: clear screen, run forward pass, print results, halt-loop
: main
    7 0 cls
    print-banner
    forward
    print-logits
    acts3 3 argmax print-prediction
    begin again ;
