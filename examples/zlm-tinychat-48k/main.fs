\ examples/zlm-tinychat-48k/main.fs — 48K with no visible side-effect.
\
\ Code + read-only data lives in the compiled image at $5C00..$F9E0.
\ Big activations are above the image, small buffers are inside it,
\ and acts3 sits in the 48K printer-buffer area which the display
\ never reads — so the screen stays clean during a forward pass.
\
\   $5B00..$5C00 (256 B)  acts3        — printer-buffer area, invisible
\   $5C00..$F9E0          image (code + W1..W4 + biases + charset
\                                 + small buffers + variables)
\   $F9E0..$FB60 (384 B)  acts2
\   $FB60..$FD60 (512 B)  acts0
\   $FD60..$FF60 (512 B)  acts1
\   $FF80          return-stack top  (32 B max, safety gap below)
\   $FFC0          data-stack   top  (32 B max)
\
\ Built with `--no-stdlib`; this file inlines the two stdlib words
\ (`cr` and `cls`) it actually uses, dropping ~200 B of unused
\ stdlib (`/`, `/mod`, `mod`, `(u.)`, `u.`, `.`, `space`, `spaces`).
\
\ Build:  zt build main.fs --target 48k --origin 0x5C00 \
\           --rstack 0xFF80 --dstack 0xFFC0 \
\           --no-inline-next --no-stdlib

\ --- minimal stdlib --------------------------------------------------

: cr  13 emit ;

: cls  ( paper ink -- )
    swap 3 lshift or
    22528 768 rot fill
    16384 6144 0 fill
    reset-cursor ;

\ --- model + buffers -------------------------------------------------

require model.fs

create query-buf  32 allot
32 constant query-max
variable query-len

create context-buf  8 allot
8 constant context-len

create acts4 80 allot

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

\ Hoisted: big activations above the image, acts3 in the printer-buffer
\ area where the display never looks. None of these consume image bytes.
$F9E0 constant acts2
$FB60 constant acts0
$FD60 constant acts1
$5B00 constant acts3

\ --- model code ------------------------------------------------------

: c@s  ( addr -- n )
    c@ dup 128 < if exit then $FF00 or ;

: arshift1  ( n -- n' )
    dup 1 rshift swap 0< if $8000 or then ;

: arshift2  ( n -- n' )    arshift1 arshift1 ;

: relu  ( n -- n' )    dup 0< if drop 0 then ;

: nth-cell  ( base i -- addr )    2 * + ;

: relu-cells ( base count -- )
    0 do  dup i nth-cell  dup @ relu swap !  loop drop ;

: linear-cell  ( wptr aptr in-count out-cell bias-ptr -- )
    >r  dup >r
    0 over !
    2bit-dot+!
    r> r> c@s over +!
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
        lp-bptr @  1+               lp-bptr !
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
    query-buf query-len @  acts0  trigram-encode
    acts0  128 2 * +  context-encode ;

: forward
    weights1  acts0  input-size   acts1  hidden1-size  bias1  linear-layer
    acts1 hidden1-size relu-cells

    weights2  acts1  hidden1-size  acts2  hidden2-size  bias2  linear-layer
    acts2 hidden2-size relu-cells

    weights3  acts2  hidden2-size  acts3  hidden3-size  bias3  linear-layer
    acts3 hidden3-size relu-cells

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

: reset-input  ( -- )    0 query-len ! ;

: input-full?  ( -- f )    query-len @ query-max = ;

: input-append  ( c -- )
    input-full? if drop exit then
    query-buf query-len @ + c!
    1 query-len +! ;

: wait-press     ( -- )    begin key? until ;
: wait-release   ( -- )    begin key? 0= until ;

: read-key  ( -- c )    wait-press key wait-release ;

: read-line  ( -- )
    reset-input
    begin
        read-key  dup 13 <>
    while
        dup emit
        input-append
    repeat
    drop ;

: main
    7 0 cls
    begin
        ." > "
        read-line
        cr
        query-len @ if chat cr then
    again ;
