\ app/title.fs — Quicksilva intro, title card, and instructions flow.
\ Colours and text placement follow Ian Andrew's BASIC line 7000 / 7081:
\   intro screens      : BORDER 1, PAPER 1 (blue), INK 7 (white)
\   instructions screen: PAPER 7 (white), INK 0 (black)

require core.fs
require screen.fs
require input.fs

require state.fs
require hud.fs

: press-any-key  ( -- )
    drain-keys wait-key drop ;

: quicksilva-banner  ( -- )
    1 border
    1 7 cls
    0  0 at-xy  ."     QUICKSILVA PRESENTS ...."
    0  5 at-xy  ."  A GAME OF STRATEGY AND SKILL !"
    0 12 at-xy  ."  OR RESCUE BILL THE WORM FROM"
    0 13 at-xy  ."        CERTAIN OLD AGE"
   21 21 at-xy  ." PRESS A KEY" ;

: title-card     ( -- )
    1 border
    1 7 cls
   11  4 at-xy  ." MINED-OUT"
   11  5 at-xy  ." ========="
    9  7 at-xy  ." by Ian Andrew"
    0 10 at-xy  ." walk to the top of the minefield"
    1 12 at-xy  ." without stepping on any mines"
    5 15 at-xy  ." keys: 6 left  7 right"
   11 16 at-xy  ." 8 down  9 up"
    2 18 at-xy  ." or CAPS+5/6/7/8 cursor keys"
   21 21 at-xy  ." PRESS A KEY" ;

: instructions   ( -- )
    1 border
    7 0 cls
   10  2 at-xy  ." INSTRUCTIONS"
   10  3 at-xy  ." ------------"
    1   5 at-xy  ." the number on the HUD shows how"
    1   6 at-xy  ." many mines touch your square."
    1   8 at-xy  ." level 2+ : rescue damsels"
    1   9 at-xy  ." level 3+ : avoid spreaders"
    1  10 at-xy  ." level 4+ : a bug follows you"
    1  11 at-xy  ." level 5+ : map may blow away"
    1  12 at-xy  ." level 8  : gap opens only when"
    1  13 at-xy  ."           you hug three mines"
    1  14 at-xy  ." level 9  : rescue bill"
    2  17 at-xy  ." bonus drops as time elapses."
    2  18 at-xy  ." clear fast for a bigger score."
   21 21 at-xy  ." PRESS A KEY" ;

: show-intro     ( -- )
    quicksilva-banner press-any-key
    title-card       press-any-key
    instructions     press-any-key ;
