\ Bitwise helpers. mod-32 wraps into a 32-entry wave table.

: mod32  ( n -- n%32 )  31 and ;
