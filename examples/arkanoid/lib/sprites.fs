\ Sprite data for arkanoid.
\
\ Layouts:
\   - ball-shifted  : 8 shifts x 16 bytes (left|right) for BLIT8X (pre-shifted ball)
\   - blank-shifted : 8 shifts x 16 bytes of zeros, used for ball erase via BLIT8X
\   - paddle-{left,mid,right} : raw 8 bytes each, char-aligned blits
\   - brick-tile, brick-blank : raw 8 bytes each, char-aligned blits
\
\ ball-shifted: each 16-byte block is one (x mod 8) sub-pixel shift of the
\ same circular ball. Shift n places the ball pixels at bit-offsets n..n+7
\ within the 16-pixel-wide window, so blit8x can render at any pixel x
\ without runtime shifting.

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

\ blank-shifted: same shape as ball-shifted (8 x 16 bytes) but all zeros,
\ so erase-ball can reuse blit8x at the same pixel position to clear pixels.
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

\ Paddle is a 3-cell strip with rounded ends. paddle-left and paddle-right
\ are mirrored caps; paddle-mid is the flat interior, drawn between them.
create paddle-left
    $00 c, $0F c, $1F c, $3F c, $3F c, $1F c, $0F c, $00 c,

create paddle-mid
    $00 c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $00 c,

create paddle-right
    $00 c, $F0 c, $F8 c, $FC c, $FC c, $F8 c, $F0 c, $00 c,

\ A brick is a single 8x8 tile drawn in row-specific colour. brick-blank
\ is reused as the all-zero sprite for clearing any cell (paddle row,
\ wall column gaps, off-brick areas).
create brick-tile
    $FF c, $81 c, $BD c, $BD c, $BD c, $BD c, $81 c, $FF c,

create brick-blank
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,

\ Walls bound the play area on the left and right (cols 0 and 31) and
\ are simply solid 8x8 blocks repeated down the column.
create wall-tile
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
