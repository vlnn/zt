\ examples/zlm-trigram/main.fs — z80ai port, tier (C): trigram encoder + canned greeting.
\
\ Hashes the canned greeting "HELLO" into 128 trigram buckets using z80ai's
\ polynomial-31, mod-65536, mod-128 algorithm (TrigramEncoder in feedme.py).
\ The 128 query buckets fill cells 0..127 of a 256-cell input vector; cells
\ 128..255 are zeroed (empty-context placeholder for tier C — the real
\ ContextEncoder lands in tier D when it has to match real model weights).
\
\ Forward pass through a synthetic 256 → 32 → 8 → 4 MLP. Argmax selects an
\ index into charset "ABCD"; the winning character is EMITted.
\
\ Weights and ground-truth predicted character come from gen_weights.py.
\
\ Build:  uv run python -m zt.cli build examples/zlm-trigram/main.fs -o build/zlm-trigram.sna
\ Run:    open build/zlm-trigram.sna in any Spectrum 48K emulator.

require weights.fs

variable te-base
variable te-len
variable te-buckets

create input-vec  512 allot
create acts1       64 allot
create acts2       16 allot
create acts3        8 allot

variable lp-in
variable lp-aptr
variable lp-wptr
variable lp-opt
variable lp-rowbytes

variable am-best-idx
variable am-best-val

: lowercase  ( c -- c' )
    dup 65 < if exit then
    dup 90 > if exit then
    32 + ;

: relu       ( n -- n' )    dup 0< if drop 0 then ;
: relu!      ( addr -- )    dup @ relu swap ! ;
: nth-cell   ( base i -- addr )    2 * + ;
: zero-cell  ( addr -- )    0 swap ! ;
: bytes-per-row  ( in-count -- bytes )    2 rshift ;

: relu-cells ( addr count -- )
    0 do  dup i nth-cell relu!  loop drop ;

: padded-char ( i -- c )
    dup 0= if drop 32 exit then
    dup te-len @ 1+ = if drop 32 exit then
    1- te-base @ + c@ lowercase ;

: hash-step ( h c -- h' )
    swap 31 *  +  $FFFF and ;

: hash3 ( c1 c2 c3 -- bucket )
    >r >r
    0 swap hash-step
    r> hash-step
    r> hash-step
    127 and ;

: trigram-at ( j -- bucket )
    dup     padded-char
    over 1+ padded-char
    rot  2 + padded-char
    hash3 ;

: trigram-encode ( str-addr str-len buckets -- )
    te-buckets !  te-len !  te-base !
    te-len @ 0 do
        1   i trigram-at 2 *  te-buckets @ +   +!
    loop ;

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
    weights1  input-vec  256  acts1  32  layer-pass
    acts1                       32       relu-cells
    weights2  acts1       32  acts2   8  layer-pass
    acts2                        8       relu-cells
    weights3  acts2        8  acts3   4  layer-pass ;

: print-banner
    0 0 at-xy  ." zlm-trigram demo (256x32x8x4)" cr
    0 1 at-xy  ." query: HELLO  charset: ABCD" ;

: print-logits
    0 4 at-xy ." logits: "
    4 0 do  acts3 i nth-cell @ .  loop ;

: print-prediction-idx ( idx -- idx )
    0 5 at-xy
    ." predicted index: " dup . ;

: print-prediction-char ( idx -- )
    0 6 at-xy
    ." predicted char:  " charset + c@ emit ;

: main
    7 0 cls
    print-banner
    input-vec 512 0 fill
    query-text query-len input-vec trigram-encode
    forward
    print-logits
    acts3 4 argmax
    print-prediction-idx
    print-prediction-char
    begin again ;
