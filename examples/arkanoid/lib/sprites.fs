\ Sprite data for arkanoid.
\
\ Layouts:
\   - ball-shifted  : 8 shifts x 16 bytes (left|right) for BLIT8X (pre-shifted ball)
\   - blank-shifted : 8 shifts x 16 bytes of zeros, used for ball erase via BLIT8X
\   - paddle-{left,mid,right} : raw 8 bytes each, char-aligned blits
\   - brick-tile, brick-blank : raw 8 bytes each, char-aligned blits

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

create paddle-left
    $00 c, $0F c, $1F c, $3F c, $3F c, $1F c, $0F c, $00 c,

create paddle-mid
    $00 c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $00 c,

create paddle-right
    $00 c, $F0 c, $F8 c, $FC c, $FC c, $F8 c, $F0 c, $00 c,

create brick-tile
    $FF c, $81 c, $BD c, $BD c, $BD c, $BD c, $81 c, $FF c,

create brick-blank
    $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c, $00 c,

create wall-tile
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
