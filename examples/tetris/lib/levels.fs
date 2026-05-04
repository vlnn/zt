\ Three preset levels.  Each is a list of 18 16-bit row bitmaps; bit n
\ in word k means "playfield cell (n, k) starts as preset debris".  The
\ load step stamps each set bit into pf-grid with the level's attribute
\ byte plus the preset marker (bit 7), then bumps preset-remaining by
\ the number of stamped cells so score.fs knows when the level's done.

require core.fs
require playfield.fs
require score.fs
require pieces.fs


\ Row bitmaps
\ ───────────
\ $3FF = all 10 cols filled; remove individual bits to leave gaps.
\
\ Level 1 — single row, one gap at col 0.  9 presets; clearable with
\ any piece reaching col 0.
\
\ Level 2 — two rows with opposite gaps (col 9 above, col 0 below).
\ 18 presets; needs at least two well-aimed pieces.
\
\ Level 3 — four rows with paired gaps mid-row.  34 presets.

create level-1-rows
    0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 ,
    0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 ,
    $3FE ,

create level-2-rows
    0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 ,
    0 , 0 , 0 , 0 , 0 , 0 , 0 ,
    $1FF , $3FE ,

create level-3-rows
    0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 , 0 ,
    0 , 0 , 0 , 0 , 0 ,
    $3DF , $3DE , $3EF , $1EF ,

\ Per-level attribute (bright + ink): green / red / magenta.

create level-attrs
    $44 c, $42 c, $43 c,


\ Resolving level → row-table
\ ───────────────────────────
\ Levels are 1-indexed in score.fs (so the HUD reads "LEVEL 1") but
\ row-table and attr arrays are 0-indexed; level-rows-addr / level-attr
\ do the translation.

: level-rows-addr  ( n -- addr )
    dup 1 = if drop level-1-rows exit then
    dup 2 = if drop level-2-rows exit then
    drop level-3-rows ;

: level-attr       ( n -- attr )
    1- level-attrs + c@ ;


\ Stamping a row bitmap into the playfield
\ ────────────────────────────────────────
\ For each set bit in the row's bitmap, write (attr | $80) into the
\ corresponding pf cell and count it for preset-remaining.

variable _stamp-row
variable _stamp-col
variable _stamp-attr
variable _stamp-count

: stamp-cell-if-set  ( bits col -- )
    _stamp-col !
    1 _stamp-col @ lshift and  if
        _stamp-attr @ cell-mark-preset
        _stamp-col @  _stamp-row @  pf!
        1 _stamp-count +!
    then ;

: stamp-row-bitmap   ( bits row -- )
    _stamp-row !
    pf-cols 0 do
        dup i stamp-cell-if-set
    loop drop ;

: load-level-rows    ( rows-addr attr -- )
    _stamp-attr !
    pf-rows 0 do
        dup i 2 *  +  @
        i stamp-row-bitmap
    loop drop ;

: load-level         ( n -- )
    pf-clear
    0 _stamp-count !
    dup level-rows-addr swap level-attr load-level-rows
    _stamp-count @ preset-set
    mark-hud-dirty ;
