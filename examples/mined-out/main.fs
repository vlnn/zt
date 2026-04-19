\ Mined-Out — faithful port of Ian Andrew's 1983 BASIC.
\
\ Coordinates:  col = 0..31, row = 0..21.  Stack order is always ( col row ).
\ Screen:
\   row 0     HUD
\   row 1     top fence, gap at cols 15..16
\   rows 2-19 playfield
\   row 20    bottom fence, gap at cols 15..16
\   row 21    safe area, player start

require app/mined.fs

: main
    init-game
    begin
        init-level
        play-loop
        end-of-level
        won? if advance-level then
    again ;
