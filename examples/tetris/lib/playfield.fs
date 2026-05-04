\ The 10x18 playfield grid.  Each byte: 0 = empty, otherwise low 7 bits
\ are the cell's attribute byte and bit 7 marks preset debris from
\ levels.fs (so line-clear can decrement the level's preset counter).
\
\ Drawing maps grid cell (col, row) to screen cell
\ (col + pf-screen-col, row + pf-screen-row).

require core.fs
require grid.fs
require screen.fs
require sprites.fs

10 constant pf-cols
18 constant pf-rows
11 constant pf-screen-col
 2 constant pf-screen-row

create pf-grid 180 allot

: pf-bind          ( -- )    pf-grid pf-cols pf-rows grid-set! ;
: pf-clear         ( -- )    0 grid-clear ;

: pf@              ( col row -- v )    grid@ ;
: pf!              ( v col row -- )    grid! ;

: cell-empty?      ( v -- flag )    0= ;
: cell-attr        ( v -- attr )    $7F and ;
: cell-preset?     ( v -- flag )    $80 and 0= 0= ;
: cell-mark-preset ( v -- v' )      $80 or ;


\ Drawing one cell
\ ────────────────
\ A non-zero cell renders as block-tile with the cell's attribute; a
\ zero cell renders as empty-tile with the background attribute so the
\ row beneath stays in step with the rest of the play area.

$00 constant pf-bg-attr

: pf-screen-of     ( col row -- scol srow )
    pf-screen-row + swap pf-screen-col + swap ;

: draw-empty-cell  ( scol srow -- )
    empty-tile pf-bg-attr 2swap blit8c ;

: draw-filled-cell ( attr scol srow -- )
    >r >r >r block-tile r> r> r> blit8c ;

: pf-draw-cell     ( col row -- )
    2dup pf@                            ( col row v )
    dup cell-empty? if
        drop pf-screen-of draw-empty-cell
    else
        cell-attr -rot pf-screen-of draw-filled-cell
    then ;

: pf-draw-row      ( row -- )
    pf-cols 0 do i over pf-draw-cell loop drop ;

: pf-draw-all      ( -- )
    pf-rows 0 do i pf-draw-row loop ;


\ Line detection and clearing
\ ───────────────────────────
\ pf-row-full? scans 10 cells; pf-row-count-presets sums bit-7s in a
\ row.  pf-compact walks bottom-to-top with src/dst pointers: a full
\ row advances src only, a non-full row copies src→dst and advances
\ both.  When src falls off the top, rows 0..dst inclusive are cleared.
\ pf-cleared-count and pf-presets-cleared expose the last compaction's
\ totals so score.fs / levels.fs can react.

variable _row-tmp
variable _ct-tmp
variable pf-src-row
variable pf-dst-row
variable pf-cleared-count
variable pf-presets-cleared

: pf-row-full?     ( row -- flag )
    -1 _row-tmp !
    pf-cols 0 do
        i over pf@ cell-empty? if 0 _row-tmp ! then
    loop drop
    _row-tmp @ ;

: pf-row-count-presets ( row -- n )
    0 _ct-tmp !
    pf-cols 0 do
        i over pf@ cell-preset? if 1 _ct-tmp +! then
    loop drop
    _ct-tmp @ ;

: pf-row-copy      ( src-row dst-row -- )
    grid-row-addr swap grid-row-addr swap pf-cols cmove ;

: pf-row-erase     ( row -- )
    grid-row-addr pf-cols 0 fill ;

: pf-compact-keep  ( -- )
    pf-src-row @ pf-dst-row @ <> if
        pf-src-row @ pf-dst-row @ pf-row-copy
    then
    -1 pf-dst-row +! ;

: pf-compact-drop  ( -- )
    pf-src-row @ pf-row-count-presets pf-presets-cleared +!
    1 pf-cleared-count +! ;

: pf-compact-step  ( -- )
    pf-src-row @ pf-row-full? if pf-compact-drop else pf-compact-keep then
    -1 pf-src-row +! ;

: pf-compact-init  ( -- )
    pf-rows 1- pf-src-row !
    pf-rows 1- pf-dst-row !
    0 pf-cleared-count !
    0 pf-presets-cleared ! ;

: pf-erase-top-rows ( -- )
    pf-dst-row @ 0< if exit then
    pf-dst-row @ 1+ 0 do i pf-row-erase loop ;

: pf-compact       ( -- )
    pf-compact-init
    begin pf-compact-step pf-src-row @ 0< until
    pf-erase-top-rows ;
