\ zlm-smoke/main.fs — profiling smoke test for the z80ai port plan.
\
\ Pairs eight packed bytes (32 signed-2bit weights, mapped via `2 -` to
\ {-2,-1,0,+1}) with eight 16-bit activations and accumulates sum-of-products
\ into a fixed-address accumulator cell.
\
\ Two implementations of the same MAC, both running the full row, so the
\ profiler can compare per-row T-states:
\
\   row-mac         — threaded `:` colon, regular dispatch each step
\   row-mac-fast    — `::` force-inline, `unpack-2bits` body spliced flat
\
\ Run:
\   zt profile --source examples/zlm-smoke/main.fs \
\              --max-ticks 200000 \
\              --words row-mac,row-mac-fast

create weights
  $1B c, $E4 c, $A5 c, $5A c,
  $00 c, $FF c, $C3 c, $3C c,

create acts
  100 ,  -50 ,    7 ,  -3 ,
   25 ,  -12 ,   80 , -64 ,
    5 ,   -2 ,    9 , -11 ,
   33 ,  -33 ,   17 , -17 ,
   42 ,  -42 ,   13 , -13 ,
   99 ,  -99 ,   21 , -21 ,
   60 ,  -60 ,   16 , -16 ,
    4 ,   -4 ,    8 ,  -8 ,

variable acc

\ MAC one signed weight against one 16-bit activation into acc.
\ ( weight act -- )
: mac1    *  acc +! ;

\ Process one packed byte against four consecutive 16-bit activations.
\ aptr lives on R-stack across the four MACs, so weights stay in their
\ natural LIFO order (u0 on top of data, paired with acts[0]).
\ ( aptr packed -- aptr+8 )
: mac4
    swap >r                                  \ R: aptr,  data: packed
    unpack-2bits                             \ R: aptr,  data: u3 u2 u1 u0
    2 -  r@ @  mac1                          \ s0 vs acts[0]
    r> 1+ 1+ >r                              \ R: aptr+2
    2 -  r@ @  mac1                          \ s1 vs acts[1]
    r> 1+ 1+ >r                              \ R: aptr+4
    2 -  r@ @  mac1                          \ s2 vs acts[2]
    r> 1+ 1+ >r                              \ R: aptr+6
    2 -  r@ @  mac1                          \ s3 vs acts[3]
    r> 1+ 1+ ;                               \ data: aptr+8

\ Force-inline variant — same algorithm, but uses `2bitmuladd` to skip
\ general 16x16 multiply, branching on weight ∈ {-2,-1,0,+1} directly.
\ Note: takes raw 0..3 (not biased), so we drop `2 -`.
:: mac4-fast
    swap >r
    unpack-2bits
    r@ @  $7FF0  2bitmuladd
    r> 1+ 1+ >r
    r@ @  $7FF0  2bitmuladd
    r> 1+ 1+ >r
    r@ @  $7FF0  2bitmuladd
    r> 1+ 1+ >r
    r@ @  $7FF0  2bitmuladd
    r> 1+ 1+ ;

: row-mac
    0 acc !
    acts                                \ aptr
    weights 8 0 do
        dup i + c@ mac4
    loop drop ;

: row-mac-fast
    0 $7FF0 !
    acts
    weights 8 0 do
        dup i + c@ mac4-fast
    loop drop ;

\ The full row in one primitive call. 8 bytes × 4 weights = 32 MACs.
: row-mac-dot
    0 $7FF0 !
    weights acts 32 $7FF0 2bit-dot+! ;

: main
    row-mac
    row-mac-fast
    row-mac-dot
    halt ;
