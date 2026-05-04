\ The intro sequence: a faithful port of Ian Andrew's three-screen
\ BASIC opening (lines 7000-7390 in the 1983 source).  Three screens
\ play in order — Quicksilva title with the mine-frame reveal, the
\ mission briefing with Bill running across the screen, and a tips
\ screen showing the controls and adjacency rules.

require core.fs
require screen.fs
require input.fs
require sounds.fs

require state.fs
require board.fs
require hud.fs


\ Common helpers
\ ──────────────
\ The intro screens share a fixed colour scheme (white-on-blue for
\ the title and mission, black-on-white for the instructions) and a
\ "press any key" prompt that drains stale keystrokes before
\ blocking.

: press-any-key  ( -- )       drain-keys wait-key drop ;
: at-row         ( row -- )   0 swap at-xy ;
: intro-colors   ( -- )       1 border  1 7 cls ;
: instr-colors   ( -- )       1 border  7 0 cls ;

: press-key-prompt  ( -- )    21 21 at-xy  ." PRESS A KEY" ;


\ Title sounds
\ ────────────
\ Two short jingles: a five-note chirp on the title appearance, and
\ a downward sweep that plays as the mine frame builds around the
\ logo.  Both are pure beep/timing — no data, just code.

: intro-chirp    ( -- )
    2 30 beep  1 20 beep
    2 26 beep  3 26 beep  2 18 beep ;

: title-beeps    ( -- )
    80 0 do  3 60 i 2 / - beep  loop ;


\ The mine frame
\ ──────────────
\ Decorative rectangle of mine glyphs framing the "MINED OUT!" logo.
\ Three components: top and bottom rows of mine glyphs, plus the two
\ side columns drawn one cell at a time.

: mine-bar       ( row -- )
    at-row  32 0 do  ch-mine emit  loop ;

: frame-sides-row  ( row -- )
    dup  0 swap at-xy ch-mine emit
         31 swap at-xy ch-mine emit ;

: frame-sides    ( -- )
    11 8 do i frame-sides-row loop ;

: draw-mine-frame  ( -- )
    7 mine-bar
    frame-sides
    11 mine-bar ;

: title-in-frame  ( -- )
   11 9 at-xy  ." MINED OUT!" ;

: tagline        ( -- )
    14 at-row  ."  OR RESCUE BILL THE WORM FROM"
    15 at-row  ."        CERTAIN OLD AGE" ;


\ Screen 1: Quicksilva title
\ ──────────────────────────
\ Matches BASIC line 7000.  Prints the publisher line, plays the
\ chirp, swaps to the strategy-and-skill subtitle, draws the mine
\ frame, sweeps the audio, prints the tagline, waits for input.

: quicksilva-screen  ( -- )
    intro-colors
    0 at-row  ."     QUICKSILVA PRESENTS ...."
    intro-chirp
    8 throttle
    0 at-row  ."  A GAME OF STRATEGY AND SKILL !"
    draw-mine-frame
    title-in-frame
    title-beeps
    tagline
    press-key-prompt
    press-any-key ;


\ The Bill scroller
\ ─────────────────
\ BASIC line 7130 holds an 85-character string with the player glyph
\ and the bug eight cells apart, surrounded by spaces.  A 32-char
\ window scrolls across it at row 6, animated by writing successive
\ slices and beeping on each step.  The buffer is built once per
\ call by filling with spaces and dropping the two glyphs into
\ fixed positions.

85 constant bill-scroll-len
52 constant bill-scroll-steps
33 constant bill-player-offset
42 constant bill-bug-offset

create bill-scroll-buf   85 allot

: init-bill-scroll  ( -- )
    bill-scroll-buf bill-scroll-len 32 fill
    ch-player bill-scroll-buf bill-player-offset + c!
    ch-bug    bill-scroll-buf bill-bug-offset    + c! ;

: bill-scroll-frame  ( offset row -- )
    at-row  bill-scroll-buf + 32 type ;

: bill-scroll-beep   ( -- )   1 60 beep ;

: scroll-bill-row  ( row -- )
    init-bill-scroll
    bill-scroll-steps 0 do
        i over bill-scroll-frame
        bill-scroll-beep
        2 throttle
    loop drop ;


\ Screen 2: mission briefing
\ ──────────────────────────
\ Matches BASIC line 7081.  The text block explains the goal of
\ rescuing Bill on level 9, then runs the Bill scroller across row
\ 6 to demonstrate the player and bug glyphs in motion.

: mission-screen  ( -- )
    instr-colors
    0  at-row  ."   (c) MINED OUT!  by Ian Andrew"
    2  at-row  ." YOUR MISSION, IF YOU ACCEPT IT,"
    3  at-row  ." IS TO RESCUE BILL THE WORM BY"
    4  at-row  ." REACHING HIM.  HE LAYS DORMANT"
    5  at-row  ." ON THE FINAL MINEFIELD, LEVEL 9."
    10 at-row  ." YOU BEGIN AT EACH LEVEL AT THE"
    11 at-row  ." BOTTOM OF THE SCREEN.  AIM FOR"
    12 at-row  ." THE GAP AT THE TOP OF THE SCREEN."
    15 at-row  ." WATCH BILL DODGE THE BUG:"
    6 scroll-bill-row
    press-key-prompt
    press-any-key ;


\ Screen 3: controls and tips
\ ───────────────────────────
\ Matches BASIC line 7200+.  Pure text, no animation: keys, the
\ adjacency rule, and a tip about safe areas.

: tips-screen    ( -- )
    instr-colors
    0  at-row  ."            CONTROLS"
    2  at-row  ." MOVE WITH:  6 left   7 right"
    3  at-row  ."             8 down   9 up"
    5  at-row  ." OR CAPS + 5/6/7/8 CURSOR KEYS."
    8  at-row  ." MINES * ARE VERY UNPLEASANT."
    10 at-row  ." THE HUD COUNTS MINES ADJACENT"
    11 at-row  ." TO YOU  (TOP LEFT OF SCREEN)."
    14 at-row  ." DAMSELS ? REGISTER AS MINES -"
    15 at-row  ." RUSH IN, RESCUE HER, GET POINTS."
    18 at-row  ." TIP: SAFE AREAS ARE MINE FREE."
    19 at-row  ." AIM FOR THEM BEFORE THE GAP."
    press-key-prompt
    press-any-key ;

: show-intro     ( -- )
    quicksilva-screen
    mission-screen
    tips-screen ;
