\ The board: tile tags, screen glyphs, the shadow grid that tracks
\ what's where, and the routines that build fences and scatter mines.
\ The grid is the source of truth for collision and adjacency
\ checks; the screen is just a view that may lag behind during
\ map-blow effects.

require core.fs
require screen.fs
require grid.fs
require rand.fs


\ Layout
\ ──────
\ The board is 32 wide × 23 tall (rows 0..22), but only rows 1..20
\ contain the playfield; row 0 is the HUD and row 22 is the banner.
\ The top and bottom fences are at fixed rows; gap-left and gap-right
\ identify the two-cell opening through which the player escapes.

32 constant board-cols
23 constant board-rows

15 constant gap-left
16 constant gap-right
0  constant left-wall-col
31 constant right-wall-col
1  constant top-fence-row
20 constant bottom-fence-row
21 constant start-row
15 constant start-col
22 constant banner-row


\ Tile tags and glyphs
\ ────────────────────
\ Each cell holds one of four tile tags.  The ch-* constants are the
\ ASCII codes for the visual glyph of every entity, so put-char and
\ its specialisations don't repeat the magic numbers.

0 constant t-empty
1 constant t-mine
2 constant t-fence
3 constant t-damsel

32 constant ch-space
35 constant ch-fence
42 constant ch-mine
79 constant ch-player
63 constant ch-damsel
37 constant ch-spreader
64 constant ch-bug
66 constant ch-bill
126 constant ch-wind


\ The shadow grid
\ ───────────────
\ Backed by 32 * 23 = 736 bytes wired into the stdlib grid.fs vocab
\ via grid-set!.  Predicates compare against the tile tags to keep
\ call sites readable.

create board-buf  736 allot

: board-init     ( -- )
    board-buf board-cols board-rows grid-set!
    t-empty grid-clear ;

: tile!          ( tag col row -- )   grid! ;
: tile@          ( col row -- tag )   grid@ ;
: empty?         ( col row -- flag )  tile@ t-empty = ;
: fence?         ( col row -- flag )  tile@ t-fence = ;
: mine?          ( col row -- flag )  tile@ t-mine  = ;
: damsel?        ( col row -- flag )  tile@ t-damsel = ;


\ Screen drawing
\ ──────────────
\ One drawing primitive per glyph type.  trail-at and wind-at also
\ paint a tinted attribute for the trail and wind effects; the rest
\ inherit the level's default attributes.

: put-char       ( ch col row -- )    at-xy emit ;
: erase-at       ( col row -- )       ch-space    -rot put-char ;
: fence-at       ( col row -- )       ch-fence    -rot put-char ;
: mine-at        ( col row -- )       ch-mine     -rot put-char ;
: player-at      ( col row -- )       ch-player   -rot put-char ;
: damsel-at      ( col row -- )       ch-damsel   -rot put-char ;
: spreader-at    ( col row -- )       ch-spreader -rot put-char ;
: bug-at         ( col row -- )       ch-bug      -rot put-char ;
: bill-at        ( col row -- )       ch-bill     -rot put-char ;

56  constant trail-attr
248 constant wind-attr

: trail-at       ( col row -- )
    2dup erase-at
    trail-attr -rot attr! ;

: wind-at        ( col row -- )
    2dup ch-wind -rot put-char
    wind-attr -rot attr! ;


\ Building fences
\ ───────────────
\ The horizontal fence has a two-cell gap at the top (cols 15..16);
\ vertical side walls bound the playfield at columns 0 and 31.
\ build-fences runs all three at level start.

: gap?           ( col -- flag )      dup gap-left = swap gap-right = or ;

: place-fence-cell  ( col row -- )
    2dup t-fence -rot tile!
    fence-at ;

: erase-cell        ( col row -- )
    2dup t-empty -rot tile!
    erase-at ;

: place-fence-at-col  ( col row -- )
    over gap? if 2drop exit then
    place-fence-cell ;

: fence-row      ( row -- )
    board-cols 0 do  i over place-fence-at-col  loop drop ;

: side-wall-row  ( row -- )
    dup  left-wall-col  swap place-fence-cell
        right-wall-col  swap place-fence-cell ;

: build-side-walls  ( -- )
    bottom-fence-row top-fence-row 1+ do i side-wall-row loop ;

: build-fences   ( -- )
    top-fence-row fence-row
    bottom-fence-row fence-row
    build-side-walls ;


\ Scattering mines
\ ────────────────
\ Random placement is naive: each attempt picks a column and row at
\ random and only places the mine if the cell is empty.  Attempts
\ that collide with an existing mine or fence are silently dropped,
\ so the actual mine count can be slightly below level-mines@ — by
\ design, it adds variety and avoids retry loops.

: rand-col       ( -- col )   board-cols random ;
: rand-interior  ( -- row )   18 random 2 + ;

: try-place-mine ( col row -- )
    2dup empty? if t-mine -rot tile! else 2drop then ;

: scatter-mines  ( n -- )
    0 do rand-col rand-interior try-place-mine loop ;


\ Mine reveal and hide
\ ────────────────────
\ Used by the cheat (which reveals everything) and by end-of-level
\ (which reveals after the win).  hide-* is for the map-blow effect:
\ erase the visible glyphs but leave the underlying tags intact, so
\ the mines are still deadly even though the player can't see them.

: reveal-cell-if-mine  ( col row -- )
    2dup mine? if mine-at else 2drop then ;

: erase-cell-if-mine   ( col row -- )
    2dup mine? if erase-at else 2drop then ;

: reveal-row     ( row -- )
    board-cols 0 do  i over reveal-cell-if-mine  loop drop ;

: show-all-mines ( -- )
    board-rows 0 do i reveal-row loop ;

: hide-mines-in-row  ( row -- )
    board-cols 0 do  i over erase-cell-if-mine  loop drop ;

: hide-all-mines ( -- )
    board-rows 0 do i hide-mines-in-row loop ;


\ The top gap
\ ───────────
\ On level 8, the top gap starts closed; the player has to stand on a
\ cell with three adjacent mines to open it.  The four words below
\ are the inspectors and mutators game.fs uses to implement that.

: top-gap-left-cell   ( -- col row )   gap-left  top-fence-row ;
: top-gap-right-cell  ( -- col row )   gap-right top-fence-row ;

: gap-open?      ( -- flag )
    top-gap-left-cell  empty?
    top-gap-right-cell empty?  and ;

: close-top-gap  ( -- )
    top-gap-left-cell  place-fence-cell
    top-gap-right-cell place-fence-cell ;

: open-top-gap   ( -- )
    top-gap-left-cell  erase-cell
    top-gap-right-cell erase-cell ;
