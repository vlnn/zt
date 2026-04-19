\ stdlib/core.fs — core Forth words built on M5 primitives

: cr     13 emit ;
: space  32 emit ;

: spaces  ( n -- )
    begin dup 0 > while 1- 32 emit repeat drop ;

: -rot    ( a b c -- c a b )   rot rot ;

\ Signed symmetric division built on unsigned u/mod.
: /mod  ( n1 n2 -- r q )
    2dup xor 0< >r
    over 0< >r
    swap abs swap abs u/mod
    r> if swap negate swap then
    r> if negate then ;

: /    /mod nip ;
: mod  /mod drop ;

\ Unsigned print, minimum necessary digits, no leading zero.
: (u.)  ( u -- )
    dup 10 u< if 48 + emit exit then
    10 u/mod recurse 48 + emit ;

: u.  (u.) space ;

: .  ( n -- )
    dup 0< if 45 emit negate then (u.) space ;

\ Spectrum screen layout:
\   pixels $4000..$57FF (6144 bytes)
\   attrs  $5800..$5AFF (768 bytes)
\ Attr byte: ink in bits 0-2, paper in bits 3-5.

: cls  ( paper ink -- )
    swap 3 lshift or       \ attr = ink | (paper << 3)
    22528 768 rot fill     \ fill attr area
    16384 6144 0 fill      \ blank pixels
    reset-cursor ;
