64 constant n
create data 128 allot
variable seed

: next-random  ( -- u )  seed @ 75 * 74 + dup seed ! ;
: cell-at  ( i -- addr )  2* data + ;
: fill-data  ( -- )  12345 seed !  n 0 do next-random i cell-at ! loop ;
: out-of-order?  ( i -- flag )  dup cell-at @ swap 1+ cell-at @ u< 0= ;
: swap-cells  ( i -- )  cell-at dup @ over 2 + @ rot tuck ! 2 + ! ;
: pass  ( -- )  n 1- 0 do i out-of-order? if i swap-cells then loop ;
: sort  ( -- )  n 0 do pass loop ;
: checksum  ( -- u )  0 n 0 do i cell-at @ i 1+ * + loop ;
: main  fill-data sort checksum halt ;
