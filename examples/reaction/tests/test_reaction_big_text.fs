include test-lib.fs
require ../lib/big-text.fs

\ Each char now renders into a 4x4 block of attribute cells.  Each cell
\ covers a 2x2 group of glyph pixels; per-cell, we look up two 8-pixel
\ row bytes from a 4-entry table indexed by the (TL,TR) and (BL,BR)
\ bit pairs.  Pixels are written to the screen and one attribute byte
\ recolours the whole cell.
\
\ TEST_FONT replicates char c as 8 identical bytes, so within any cell
\ of any glyph the top half and bottom half are the same byte.
\
\   65 = 'A'  = 0b01000001 → leading=1, shifted=0b10000010
\     cell-col 0: bits 7,6 of $82 = (1, 0) → idx=2 → $F0
\     cell-col 1: bits 5,4         = (0, 0) → idx=0 → $00
\     cell-col 2: bits 3,2         = (0, 0) → idx=0 → $00
\     cell-col 3: bits 1,0         = (1, 0) → idx=2 → $F0


: clear-screen   0 fill-attrs   16384 6144 0 fill ;
: prep-render    clear-screen   $7F big-colours ;


\ ── lookup table & bit-extract helpers ─────────────────────────────

: test-half-row-table-zero
    0 half-row-byte + c@   $00 assert-eq ;

: test-half-row-table-right
    1 half-row-byte + c@   $0F assert-eq ;

: test-half-row-table-left
    2 half-row-byte + c@   $F0 assert-eq ;

: test-half-row-table-both
    3 half-row-byte + c@   $FF assert-eq ;


: test-cell-bits-cc-0
    \ $C0 = bits 7,6 set → cell-col 0 sees (1,1) = idx 3
    $C0 0 cell-bits   3 assert-eq ;

: test-cell-bits-cc-1
    \ $C0 → cell-col 1 sees bits 5,4 = (0,0) = 0
    $C0 1 cell-bits   0 assert-eq ;

: test-cell-bits-cc-3-rightmost
    \ $03 = bits 1,0 set → cell-col 3 sees (1,1) = 3
    $03 3 cell-bits   3 assert-eq ;

: test-cell-bits-mixed
    \ $A4 = 0b10100100 → cc 0 sees (1,0)=2, cc 1 sees (1,0)=2, cc 2 sees (0,1)=1, cc 3 sees (0,0)=0
    $A4 0 cell-bits   2 assert-eq ;


\ ── pixel addressing ───────────────────────────────────────────────

: test-cell-pix-addr-origin
    0 0 cell-pix-addr   $4000 assert-eq ;

: test-cell-pix-addr-col-1
    1 0 cell-pix-addr   $4001 assert-eq ;

: test-cell-pix-addr-row-1-same-band
    \ row 1 within band 0: in-band=1 → +32
    0 1 cell-pix-addr   $4020 assert-eq ;

: test-cell-pix-addr-row-8-next-band
    \ row 8 = band 1, in-band 0 → +2048
    0 8 cell-pix-addr   $4800 assert-eq ;

: test-cell-pix-addr-row-23-last-band
    \ row 23 = band 2 (= +4096), in-band 7 (= +224)
    0 23 cell-pix-addr   $4000 4096 + 224 + assert-eq ;


\ ── leading-blanks (kept from the 8x8 renderer) ────────────────────

: test-leading-blanks-A
    65 leading-blanks   1 assert-eq ;

: test-leading-blanks-zero-digit
    48 leading-blanks   2 assert-eq ;


\ ── big-emit pixel writes for 'A' at (0, 0) ────────────────────────
\ After the leading-blank shift, 'A' light pixels in cells (0,_) and
\ (3,_) on its left half (TL).  Cell (0, cell-row=0) covers pixel
\ rows 0..7, with pixel-row addresses $4000, $4100, … $4700.

: test-big-emit-A-cell-0-line-0
    prep-render
    65 0 0 big-emit
    $4000 c@   $F0 assert-eq ;

: test-big-emit-A-cell-0-line-3
    prep-render
    65 0 0 big-emit
    $4300 c@   $F0 assert-eq ;

: test-big-emit-A-cell-0-line-4
    \ Bottom half of cell — TEST_FONT replicates the row, so same byte.
    prep-render
    65 0 0 big-emit
    $4400 c@   $F0 assert-eq ;

: test-big-emit-A-cell-1-blank
    \ Cell (1, 0) starts at pix col 1 → pixel addr $4001.  Cell-col 1
    \ of 'A' is blank, so the byte at $4001 stays $00.
    prep-render
    65 0 0 big-emit
    $4001 c@   $00 assert-eq ;

: test-big-emit-A-cell-3-line-0
    \ Cell (3, 0) → pixel addr $4003 (pix col 3 of band 0 row 0).
    prep-render
    65 0 0 big-emit
    $4003 c@   $F0 assert-eq ;

: test-big-emit-A-cell-row-1-line-0
    \ Cell (0, 1) → in-band=1, pixel addr $4020 line 0.
    prep-render
    65 0 0 big-emit
    $4020 c@   $F0 assert-eq ;

: test-big-emit-A-cell-row-3-line-7
    \ Cell (0, 3) → pixel addr $4060 line 0; line 7 is +1792 → $4760.
    prep-render
    65 0 0 big-emit
    $4760 c@   $F0 assert-eq ;

: test-big-emit-A-no-paint-cell-row-4
    \ Char only spans 4 cell-rows, so cell-row 4 (pix addr $4080) stays $00.
    prep-render
    65 0 0 big-emit
    $4080 c@   $00 assert-eq ;


\ ── attributes apply to every cell of the char ─────────────────────

: test-big-emit-attr-cell-0-0
    prep-render
    65 0 0 big-emit
    0 0 attr@   $7F assert-eq ;

: test-big-emit-attr-cell-3-3
    prep-render
    65 0 0 big-emit
    3 3 attr@   $7F assert-eq ;

: test-big-emit-attr-outside-block-untouched
    prep-render
    65 0 0 big-emit
    4 0 attr@   0 assert-eq ;


\ ── '0' digit rendering ─────────────────────────────────────────────
\ '0' = 0b00110000 → leading=2, shifted=0b11000000=$C0.
\ Per cell-col: cc=0 → bits 7,6 = (1,1) → idx 3 → $FF; cc=1..3 → $00.

: test-big-emit-zero-digit-cell-0-full
    prep-render
    48 0 0 big-emit
    $4000 c@   $FF assert-eq ;

: test-big-emit-zero-digit-cell-1-blank
    prep-render
    48 0 0 big-emit
    $4001 c@   $00 assert-eq ;


\ ── col / row offsets ──────────────────────────────────────────────

: test-big-emit-honours-col-offset
    \ Char at base col 5 → cell (5, 0) → pix addr $4005.
    prep-render
    65 5 0 big-emit
    $4005 c@   $F0 assert-eq ;

: test-big-emit-honours-row-offset
    \ Char at base row 4 → cell (0, 4) → in-band=4 → +128 → pix addr $4080.
    prep-render
    65 0 4 big-emit
    $4080 c@   $F0 assert-eq ;


\ ── big-type advances 4 cells per char ─────────────────────────────

: test-big-type-second-char-four-cells-right
    \ 'B' at base col 4 → first cell at pix addr $4004.
    \ 'B' = 66 = 0b01000010 → leading=1, shifted=0b10000100=$84.
    \ Cell-col 0 of B: bits 7,6 = (1,0) → idx 2 → $F0.
    prep-render
    s" AB" 0 0 big-type
    $4004 c@   $F0 assert-eq ;

: test-big-type-first-char-still-at-base
    prep-render
    s" AB" 0 0 big-type
    $4000 c@   $F0 assert-eq ;

: test-big-type-respects-row-offset
    \ At row offset 4 → in-band=4 → pix addr $4080.
    prep-render
    s" AB" 0 4 big-type
    $4080 c@   $F0 assert-eq ;


\ ── regression: bottom half of cell-row r must read glyph row 2r+1 ─

: test-bottom-half-uses-glyph-row-2r-plus-1
    \ Override glyph rows 1 and 3 of 'X' with distinct bytes that
    \ choose different lookup-table entries.  TEST_FONT leaves rows 0,
    \ 2, 4..7 as $58 (= 'X'); the OR over the glyph keeps the same
    \ leading-blanks=1 so the shift is the same as for plain 'X'.
    \ Cell (cell-col=0, cell-row=1) reads glyph rows 2 (top) and 3
    \ (bottom).  Earlier code mistakenly read row 1 for the bottom,
    \ which would land $80 at the bottom half instead of $40.
    \   row 1 byte = $40 → after shift 1: $80 → cc=0 bits = (1,0) → $F0
    \   row 3 byte = $20 → after shift 1: $40 → cc=0 bits = (0,1) → $0F
    \ So a correct renderer leaves $0F at the cell-row-1 bottom-half
    \ pixel address; a buggy one leaves $F0.
    $40 $3EC1 c!
    $20 $3EC3 c!
    prep-render
    88 0 0 big-emit
    $4420 c@   $0F assert-eq ;
