: cell-addr   ( col row -- addr )  32 * + 22528 + ;
: attr        ( col row -- val )   and 0= if 56 else 0 then ;
: plot        ( col row -- )       2dup cell-addr >r attr r> c! ;
: line        ( row -- )           32 0 do  i over plot  loop drop ;
: sierpinski  ( -- )               24 0 do  i line       loop ;
: main 1 begin dup border sierpinski 1+ again ;
