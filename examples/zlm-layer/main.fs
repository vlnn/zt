\ examples/zlm-layer/main.fs — z80ai port, tier (A): single-layer forward-pass.
\
\ A 32-input × 4-output linear layer with 2-bit signed weights and 16-bit
\ signed activations, exactly matching z80ai's MAC convention. Computes
\ outputs[i] = ReLU( sum( weight[i,j] * activation[j] ) ) for j in 0..31.
\
\ Random seed=42 (Python `random.randint`) — expected outputs are 377, 1135,
\ 190, 1175 (verified independently in Python).
\
\ Build:  uv run python -m zt.cli build examples/zlm-layer/main.fs -o build/zlm-layer.sna
\ Run:    open build/zlm-layer.sna in any Spectrum 48K emulator (FUSE, ZEsarUX, ...)

create activations
  -71 , -116 , 12 , -3 ,
  -14 , -57 , -76 , -84 ,
  88 , -112 , -113 , -81 ,
  -17 , -9 , -115 , -27 ,
  86 , -16 , 101 , 14 ,
  -125 , -47 , 88 , 46 ,
  14 , -49 , -18 , 44 ,
  -76 , -81 , 66 , -79 ,

create weights
  $2A c, $33 c, $1A c, $24 c, $B1 c, $9B c, $26 c, $D5 c,    \ output 0
  $9B c, $84 c, $4B c, $F6 c, $67 c, $F9 c, $D6 c, $40 c,    \ output 1
  $CD c, $2F c, $28 c, $DE c, $18 c, $96 c, $E1 c, $A0 c,    \ output 2
  $11 c, $4C c, $9D c, $97 c, $FB c, $14 c, $52 c, $40 c,    \ output 3

create outputs 0 , 0 , 0 , 0 ,

8 constant bytes-per-row
32 constant inputs-per-row

: weight-row  ( i -- wptr )    bytes-per-row * weights + ;
: output-cell ( i -- addr )    2 * outputs + ;

: relu  ( n -- n' )    dup 0< if drop 0 then ;

: relu!  ( addr -- )    dup @ relu swap ! ;

: forward
    4 0 do
        0 i output-cell !
        i weight-row activations inputs-per-row i output-cell 2bit-dot+!
        i output-cell relu!
    loop ;

: print-output  ( i -- )
    dup 0 swap 4 + at-xy
    ." out " dup . ." : "
    output-cell @ . cr ;

: print-results
    0 0 at-xy  ." zlm-layer demo (32x4)" cr
    0 1 at-xy  ." expected: 377 1135 190 1175"
    4 0 do i print-output loop ;

: main
    7 0 cls
    forward
    print-results
    begin again ;
