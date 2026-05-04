\ Sprite data for arkanoid: the pre-shifted ball, an all-zero blank
\ (also pre-shifted), the three-cell paddle strip, the brick tile, and
\ the side-wall tile.  Pre-shifted layout for 8x8 sprites is 8 shift
\ positions × 16 bytes (8 rows × 2 bytes left|right) = 128 bytes; for
\ shift s and source byte b, left = b >> s and right = (b << (8-s))
\ & $FF.  blit8x picks the right shift block from the low 3 bits of
\ the destination x.


\ The ball
\ ────────
\ Pre-shifted so blit8x can render at any pixel x without runtime
\ shifting.  blank-shifted has identical shape but all zeros; erasing
\ at the same coordinates would clear the same window, but game.fs
\ instead does cell-level restore so it can repaint bricks underneath.

create ball-shifted
    $3C c, $00 c, $7E c, $00 c, $FF c, $00 c, $FF c, $00 c,
    $FF c, $00 c, $FF c, $00 c, $7E c, $00 c, $3C c, $00 c,
    $1E c, $00 c, $3F c, $00 c, $7F c, $80 c, $7F c, $80 c,
    $7F c, $80 c, $7F c, $80 c, $3F c, $00 c, $1E c, $00 c,
    $0F c, $00 c, $1F c, $80 c, $3F c, $C0 c, $3F c, $C0 c,
    $3F c, $C0 c, $3F c, $C0 c, $1F c, $80 c, $0F c, $00 c,
    $07 c, $80 c, $0F c, $C0 c, $1F c, $E0 c, $1F c, $E0 c,
    $1F c, $E0 c, $1F c, $E0 c, $0F c, $C0 c, $07 c, $80 c,
    $03 c, $C0 c, $07 c, $E0 c, $0F c, $F0 c, $0F c, $F0 c,
    $0F c, $F0 c, $0F c, $F0 c, $07 c, $E0 c, $03 c, $C0 c,
    $01 c, $E0 c, $03 c, $F0 c, $07 c, $F8 c, $07 c, $F8 c,
    $07 c, $F8 c, $07 c, $F8 c, $03 c, $F0 c, $01 c, $E0 c,
    $00 c, $F0 c, $01 c, $F8 c, $03 c, $FC c, $03 c, $FC c,
    $03 c, $FC c, $03 c, $FC c, $01 c, $F8 c, $00 c, $F0 c,
    $00 c, $78 c, $00 c, $FC c, $01 c, $FE c, $01 c, $FE c,
    $01 c, $FE c, $01 c, $FE c, $00 c, $FC c, $00 c, $78 c,

create blank-shifted
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,


\ The paddle
\ ──────────
\ Three char-aligned cells: rounded left cap, flat middle, rounded
\ right cap.  Drawn with three blit8 calls in paddle.fs.

create paddle-left
    $00 c, $0F c, $1F c, $3F c, $3F c, $1F c, $0F c, $00 c,

create paddle-mid
    $00 c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $00 c,

create paddle-right
    $00 c, $F0 c, $F8 c, $FC c, $FC c, $F8 c, $F0 c, $00 c,


\ Bricks and walls
\ ────────────────
\ A brick is a single 8x8 tile drawn in row-specific colour (set in
\ bricks.fs).  brick-blank doubles as the all-zero sprite for clearing
\ any cell — paddle row, off-brick areas, and wall column gaps.
\ wall-tile is a solid byte stamped down the left and right columns.

create brick-tile
    $FF c, $81 c, $BD c, $BD c, $BD c, $BD c, $81 c, $FF c,

create brick-blank
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,

create wall-tile
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
