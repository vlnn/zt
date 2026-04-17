\ examples/hello.fs — M5 demo: string output, number formatting, loops.

: banner
    ." ==================" cr
    ."   FORTH ON Z80"     cr
    ."   cross-compiled"   cr
    ." ==================" cr ;

: count-to-ten
    11 1 do i . loop cr ;

: hello
    7 0 cls
    banner
    ." counting: " count-to-ten
    ." goodbye!" cr ;

: main  hello begin again ;
