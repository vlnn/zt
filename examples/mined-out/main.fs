\ Mined-Out — faithful port of Ian Andrew's 1983 BASIC.  The player
\ navigates a minefield from the bottom of the screen to the gap at
\ the top, with only an adjacency count to guess where the mines are.
\ Later levels add damsels to rescue, a mine-spreader, a stalking bug,
\ wind that drifts the player, a map-blow effect, a closed top gap,
\ and finally a Bill-rescue chamber on level 9.
\
\ Coordinates: col = 0..31, row = 0..21.  Stack order is always
\ ( col row ).  Screen layout:
\
\   row 0     HUD
\   row 1     top fence, gap at cols 15..16
\   rows 2-19 playfield
\   row 20    bottom fence, gap at cols 15..16
\   row 21    safe area, player start

require app/mined.fs

: main
    init-game
    show-intro
    begin
        init-level
        play-loop
        end-of-level
        continue-or-restart
    again ;
