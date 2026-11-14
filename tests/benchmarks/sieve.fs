2000 constant size
create flags size allot

: clear-flags  ( -- )  size 0 do 1 flags i + c! loop ;
: strike  ( prime -- )  dup 2* begin dup size < while 0 over flags + c! over + repeat 2drop ;
: sieve  ( -- count )
    clear-flags 0
    size 2 do
        flags i + c@ if i strike 1+ then
    loop ;
: main  sieve halt ;
