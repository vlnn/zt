\ Sprite data: a filled tetris block with a one-pixel highlight border,
\ an empty tile for erasing, and a wall tile for the playfield border.
\ All char-aligned 8x8 — pieces are drawn one cell per mino with blit8c
\ so the colour comes from a per-piece attribute byte.

create block-tile
    $FF c, $FF c, $C3 c, $C3 c, $C3 c, $C3 c, $FF c, $FF c,

create empty-tile
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,

create wall-tile
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
