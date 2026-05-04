\ stdlib/core.fs — core Forth words built on M5 primitives

\ emit a carriage return
: cr     13 emit ;
\ emit a single space
: space  32 emit ;

\ emit n spaces
: spaces  ( n -- )
    begin dup 0 > while 1- 32 emit repeat drop ;

\ rotate top three stack items in the opposite direction of rot
: -rot    ( a b c -- c a b )   rot rot ;

\ Conditional duplicate: leave a copy of TOS only when it is non-zero.
\ Standard Forth idiom for "consume value or leave for further use" — see
\ play-or-mute-* in examples/im2-bach.  Single-dispatch primitive: the
\ `or h` after `ld a, l` sets Z iff both halves of HL are zero.
::: ?dup  ( n -- 0 | n n )
    ld_a_l or_h
    jr_z skip
    push_hl
    label skip ;

\ Signed symmetric division built on unsigned u/mod.
: /mod  ( n1 n2 -- r q )
    2dup xor 0< >r
    over 0< >r
    swap abs swap abs u/mod
    r> if swap negate swap then
    r> if negate then ;

\ signed integer division, quotient only
: /    /mod nip ;
\ signed integer modulo, remainder only
: mod  /mod drop ;

\ Unsigned print, minimum necessary digits, no leading zero.
: (u.)  ( u -- )
    dup 10 u< if 48 + emit exit then
    10 u/mod recurse 48 + emit ;

\ print unsigned number followed by a space
: u.  (u.) space ;

\ print signed number followed by a space
: .  ( n -- )
    dup 0< if 45 emit negate then (u.) space ;

\ Spectrum screen layout:
\   pixels $4000..$57FF (6144 bytes)
\   attrs  $5800..$5AFF (768 bytes)
\ Attr byte: ink in bits 0-2, paper in bits 3-5.

\ clear screen with given paper and ink colours, and reset cursor
: cls  ( paper ink -- )
    swap 3 lshift or       \ attr = ink | (paper << 3)
    22528 768 rot fill     \ fill attr area
    16384 6144 0 fill      \ blank pixels
    reset-cursor ;

\ ── Canonical struct field-access patterns ────────────────────────────────
\
\ Force-inline (`::`) so the unfused fallback emits native `+ @` body bytes
\ at the call site instead of incurring a colon-call. With fusion on (the
\ default), the recognizer detects the 3-token form
\
\   record .field >@      kitchen .north >@
\   actor  .x     >@      \\ inside an accessor colon, dynamic instance
\
\ and replaces it with one Z80 absolute-load (static instance) or
\ offset-add+deref (dynamic instance). The colon definitions below are
\ never actually called when fusion is on.
\
\ Prefix shape was chosen because the conventional `+!` is taken by Forth's
\ increment-store ( x addr -- mem[addr]+=x ); `>@` and `>!` read naturally
\ as 'with-offset, fetch / store' and don't collide with `>` (comparison),
\ since `>@` is a single token.

:: >@   ( addr offset -- value )    + @  ;
:: >!   ( value addr offset -- )    + !  ;
:: >c@  ( addr offset -- byte )     + c@ ;
:: >c!  ( byte addr offset -- )     + c! ;
