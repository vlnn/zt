\ Bitwise helpers.  mod32 wraps any integer into the [0, 32) range so
\ it can index the 32-entry wave table.

: mod32  ( n -- n%32 )  31 and ;
