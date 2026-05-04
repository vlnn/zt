\ z80ai's tinychat, ported to zt.  A four-layer neural net runs
\ entirely in Z80 integer arithmetic, taking a 256-cell input vector
\ (128 query buckets + 128 context buckets) through hidden layers of
\ 256 → 192 → 128 cells to a 40-way output.  Each layer is a dot
\ product plus bias, wrapped to 16 bits, arithmetic-shift-right by
\ two, then ReLU (skipped on the final layer).  Argmax over the 40
\ logits picks an output character, which is emitted and appended to
\ the rolling context window before the loop repeats.
\
\ Weights live in 128K RAM banks 0/1/3/4 — one layer per bank, each
\ paged into $C000 when its layer runs.  This is what makes the
\ whole model fit on a Spectrum 128 at all.
\
\ Build: zt build examples/zlm-tinychat/main.fs -o build/zlm-tinychat.sna --target 128k
\ Open in any Spectrum 128 emulator and watch a chatbot from 1976 say HI.

require model.fs

create query-buf  32 allot
32 constant query-max
variable query-len

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

\ arithmetic right shift by one (preserves sign bit)
: arshift1  ( n -- n' )
    dup 1 rshift swap 0< if $8000 or then ;

\ arithmetic right shift by two
: arshift2  ( n -- n' )    arshift1 arshift1 ;

\ rectified linear: clamp negative inputs to zero
: relu  ( n -- n' )    dup 0< if drop 0 then ;

\ address of the i-th 16-bit cell of base
: nth-cell  ( base i -- addr )    2 * + ;

\ apply ReLU element-wise to count cells starting at base
: relu-cells ( base count -- )
    0 do  dup i nth-cell  dup @ relu swap !  loop drop ;

\ compute one output cell: dot product, add bias, arshift2 in place
: linear-cell  ( wptr aptr in-count out-cell bias-cell -- )
    >r  dup >r
    0 over !
    2bit-dot+!
    r> r> @ over +!
    dup @ arshift2 swap ! ;

\ run a full linear layer (dot + bias + scale) into opt-base
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

\ map an ASCII character to lowercase, leaving non-letters untouched
: lowercase  ( c -- c' )
    dup 65 < if exit then
    dup 90 > if exit then
    32 + ;

\ fetch the encoder character at position p (1-based), padding ends with space
: padded-char  ( p -- c )
    dup 0= if drop 32 exit then
    dup enc-len @ 1+ = if drop 32 exit then
    1- enc-base @ + c@ ;

\ hash the trigram beginning at position p into one of 128 buckets
: hash-tri-at  ( p -- bucket )
    0
    3 0 do
        over i + padded-char lowercase
        swap 31 * + $FFFF and
    loop
    nip 127 and ;

\ accumulate trigram-bucket counts for a query string into an activation slab
: trigram-encode  ( str-addr str-len buckets -- )
    enc-buckets !
    enc-len !
    enc-base !
    enc-len @ 0 do
        i hash-tri-at
        2 *  enc-buckets @  +
        32 swap +!
    loop ;

\ lowercased character from the context buffer at index i
: ctx-char  ( i -- c )    context-buf + c@ lowercase ;

\ hash an n-gram starting at index i in the context into a 128-bucket slot
: ctx-hash-ng  ( i n -- bucket )
    over 7 * $FFFF and ctx-h !
    0 do
        dup i + ctx-char
        ctx-h @ 31 * + $FFFF and ctx-h !
    loop
    drop
    ctx-h @ 127 and ;

\ accumulate context-bucket counts for every n-gram of length n
: ctx-encode-n  ( n -- )
    dup ctx-n !
    context-len swap - 1+
    0 do
        i ctx-n @ ctx-hash-ng
        2 *  ctx-buckets @  +
        32 swap +!
    loop ;

\ encode the context as a mix of 1-, 2- and 3-grams
: context-encode  ( buckets -- )
    ctx-buckets !
    1 ctx-encode-n
    2 ctx-encode-n
    3 ctx-encode-n ;

\ fill the context buffer with spaces
: clear-context  context-buf context-len 32 fill ;

\ slide the context window one cell left
: shift-context-left
    context-buf 1+  context-buf  context-len 1-  cmove ;

\ append a character to the context, dropping the oldest
: append-context  ( c -- )
    shift-context-left
    context-buf context-len 1- + c! ;

\ zero out the input activation slab
: zero-input
    acts0  input-size 2 *  0 fill ;

\ encode the query (first 128 buckets) and context (next 128) into acts0
: encode-input
    zero-input
    query-buf query-len @  acts0  trigram-encode
    acts0  128 2 * +  context-encode ;

\ run all four layers, paging in the right bank for each one
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

\ index of the largest cell in a count-cell vector at base
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

\ map the final argmax through the charset to produce the next character
: predict-char  ( -- c )
    acts4 output-size argmax
    charset + c@ ;

\ generate up to 16 characters of reply, stopping on the null terminator
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

\ clear the query buffer
: reset-input  ( -- )    0 query-len ! ;

\ true if the query buffer is at capacity
: input-full?  ( -- f )    query-len @ query-max = ;

\ append c to the query buffer (silently dropped if full)
: input-append  ( c -- )
    input-full? if drop exit then
    query-buf query-len @ + c!
    1 query-len +! ;

\ block until any key is pressed
: wait-press     ( -- )    begin key? until ;
\ block until no key is held
: wait-release   ( -- )    begin key? 0= until ;

\ wait for a keypress and return its character (with debounce)
: read-key  ( -- c )    wait-press key wait-release ;

\ read characters into the query buffer until ENTER, echoing as typed
: read-line  ( -- )
    reset-input
    begin
        read-key  dup 13 <>
    while
        dup emit
        input-append
    repeat
    drop ;

\ entry point: prompt, read a line, generate a reply, repeat forever
: main
    7 0 cls
    begin
        ." > "
        read-line
        cr
        query-len @ if chat cr then
    again ;
