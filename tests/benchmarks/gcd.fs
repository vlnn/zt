variable acc
: gcd  ( a b -- g )
    begin 2dup <> while
        2dup > if swap over - swap else over - then
    repeat drop ;
: sum-gcds  ( -- )  0 acc !  40 1 do 40 1 do i j gcd acc +! loop loop ;
: main  sum-gcds acc @ halt ;
