\ examples/zlm-tinychat/main.fs — z80ai's tinychat ported to zt.
\
\ Architecture: 256 (128 query + 128 context buckets) → 256 → 192 → 128 → 40.
\ Weights live in 128K banks 0/1/3/4 (one layer each, $C000 in their bank).
\ Per layer: dot → +bias → 16-bit wrap → arshift2 → ReLU (skip ReLU on final).
\ Argmax over 40 logits → charset lookup → EMIT → append to context → repeat.
\
\ Build: zt build examples/zlm-tinychat/main.fs -o build/zlm-tinychat.sna --target 128k
\ Open in any Spectrum 128 emulator and watch a chatbot from 1976 say HI.

require model.fs

create query-text  $48 c, $45 c, $4C c, $4C c, $4F c,    \ "HELLO"
5 constant query-len

8 constant context-len
create context-buf  8 allot

create acts0  512 allot       \ 256 cells
create acts1  512 allot       \ 256 cells
create acts2  384 allot       \ 192 cells
create acts3  256 allot       \ 128 cells
create acts4   80 allot       \  40 cells

variable lp-wptr
variable lp-aptr
variable lp-in
variable lp-rowbytes
variable lp-opt
variable lp-bptr

variable enc-base
variable enc-len
variable enc-buckets
variable ctx-buckets
variable ctx-h
variable ctx-n

variable am-best-idx
variable am-best-val

: arshift1  ( n -- n' )
    dup 1 rshift swap 0< if $8000 or then ;

: arshift2  ( n -- n' )    arshift1 arshift1 ;

: relu  ( n -- n' )    dup 0< if drop 0 then ;

: nth-cell  ( base i -- addr )    2 * + ;

: relu-cells ( base count -- )
    0 do  dup i nth-cell  dup @ relu swap !  loop drop ;

: linear-cell  ( wptr aptr in-count out-cell bias-cell -- )
    >r  dup >r
    0 over !
    2bit-dot+!
    r> r> @ over +!
    dup @ arshift2 swap ! ;

: linear-layer  ( wptr aptr in-count opt-base out-count bptr -- )
    lp-bptr !
    >r
    lp-opt !
    dup lp-in !
    2 rshift lp-rowbytes !
    lp-aptr !
    lp-wptr !
    r> 0 do
        lp-wptr @
        lp-aptr @
        lp-in   @
        lp-opt  @
        lp-bptr @
        linear-cell
        lp-wptr @  lp-rowbytes @ +  lp-wptr !
        lp-opt  @  2 +              lp-opt  !
        lp-bptr @  2 +              lp-bptr !
    loop ;

: lowercase  ( c -- c' )
    dup 65 < if exit then
    dup 90 > if exit then
    32 + ;

: padded-char  ( p -- c )
    dup 0= if drop 32 exit then
    dup enc-len @ 1+ = if drop 32 exit then
    1- enc-base @ + c@ ;

: hash-tri-at  ( p -- bucket )
    0
    3 0 do
        over i + padded-char lowercase
        swap 31 * + $FFFF and
    loop
    nip 127 and ;

: trigram-encode  ( str-addr str-len buckets -- )
    enc-buckets !
    enc-len !
    enc-base !
    enc-len @ 0 do
        i hash-tri-at
        2 *  enc-buckets @  +
        32 swap +!
    loop ;

: ctx-char  ( i -- c )    context-buf + c@ lowercase ;

: ctx-hash-ng  ( i n -- bucket )
    over 7 * $FFFF and ctx-h !
    0 do
        dup i + ctx-char
        ctx-h @ 31 * + $FFFF and ctx-h !
    loop
    drop
    ctx-h @ 127 and ;

: ctx-encode-n  ( n -- )
    dup ctx-n !
    context-len swap - 1+
    0 do
        i ctx-n @ ctx-hash-ng
        2 *  ctx-buckets @  +
        32 swap +!
    loop ;

: context-encode  ( buckets -- )
    ctx-buckets !
    1 ctx-encode-n
    2 ctx-encode-n
    3 ctx-encode-n ;

: clear-context  context-buf context-len 32 fill ;

: shift-context-left
    context-buf 1+  context-buf  context-len 1-  cmove ;

: append-context  ( c -- )
    shift-context-left
    context-buf context-len 1- + c! ;

: zero-input
    acts0  input-size 2 *  0 fill ;

: encode-input
    zero-input
    query-text query-len  acts0  trigram-encode
    acts0  128 2 * +  context-encode ;

: forward
    bank-fc1 bank!
    weights1  acts0  input-size   acts1  hidden1-size  bias1  linear-layer
    acts1 hidden1-size relu-cells

    bank-fc2 bank!
    weights2  acts1  hidden1-size  acts2  hidden2-size  bias2  linear-layer
    acts2 hidden2-size relu-cells

    bank-fc3 bank!
    weights3  acts2  hidden2-size  acts3  hidden3-size  bias3  linear-layer
    acts3 hidden3-size relu-cells

    bank-fc4 bank!
    weights4  acts3  hidden3-size  acts4  output-size   bias4  linear-layer ;

: argmax  ( base count -- idx )
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

: predict-char  ( -- c )
    acts4 output-size argmax
    charset + c@ ;

: chat
    clear-context
    16 0 do
        encode-input
        forward
        predict-char
        dup 0= if drop unloop exit then
        dup emit
        append-context
    loop ;

: main
    7 0 cls
    0 0 at-xy ." > " query-text query-len type cr
    chat
    cr
    begin again ;
