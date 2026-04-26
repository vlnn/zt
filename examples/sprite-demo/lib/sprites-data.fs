\ Sprite data for the demo: smiley, smiley pre-shifted, and three ship pieces.
\
\ Layouts:
\   - smiley:         8 raw bytes, row 0 first         (for BLIT8 / BLIT8C)
\   - smiley-shifted: 8 shifts x 16 bytes (left|right) (for BLIT8X / BLIT8XC)
\   - ship-{nose,body,tail}: each a 128-byte pre-shifted block

\ -- 8x8 raw smiley ----------------------------------------------------------
create smiley
    $3C c, $42 c, $A5 c, $81 c, $A5 c, $99 c, $42 c, $3C c,

\ -- Pre-shifted smiley (128 bytes) ------------------------------------------
\ Per shift block: row0_left row0_right row1_left row1_right ...
\ For shift s, source byte b at row r:
\   left  = b >> s
\   right = (b << (8 - s)) & $FF
create smiley-shifted
    $3C c, $00 c, $42 c, $00 c, $A5 c, $00 c, $81 c, $00 c,
    $A5 c, $00 c, $99 c, $00 c, $42 c, $00 c, $3C c, $00 c,
    $1E c, $00 c, $21 c, $00 c, $52 c, $80 c, $40 c, $80 c,
    $52 c, $80 c, $4C c, $80 c, $21 c, $00 c, $1E c, $00 c,
    $0F c, $00 c, $10 c, $80 c, $29 c, $40 c, $20 c, $40 c,
    $29 c, $40 c, $26 c, $40 c, $10 c, $80 c, $0F c, $00 c,
    $07 c, $80 c, $08 c, $40 c, $14 c, $A0 c, $10 c, $20 c,
    $14 c, $A0 c, $13 c, $20 c, $08 c, $40 c, $07 c, $80 c,
    $03 c, $C0 c, $04 c, $20 c, $0A c, $50 c, $08 c, $10 c,
    $0A c, $50 c, $09 c, $90 c, $04 c, $20 c, $03 c, $C0 c,
    $01 c, $E0 c, $02 c, $10 c, $05 c, $28 c, $04 c, $08 c,
    $05 c, $28 c, $04 c, $C8 c, $02 c, $10 c, $01 c, $E0 c,
    $00 c, $F0 c, $01 c, $08 c, $02 c, $94 c, $02 c, $04 c,
    $02 c, $94 c, $02 c, $64 c, $01 c, $08 c, $00 c, $F0 c,
    $00 c, $78 c, $00 c, $84 c, $01 c, $4A c, $01 c, $02 c,
    $01 c, $4A c, $01 c, $32 c, $00 c, $84 c, $00 c, $78 c,

\ -- Ship pieces for MULTI-BLIT (each pre-shifted, 128 bytes) ----------------
create ship-nose
    $07 c, $00 c, $1F c, $00 c, $7F c, $00 c, $FF c, $00 c,
    $FF c, $00 c, $7F c, $00 c, $1F c, $00 c, $07 c, $00 c,
    $03 c, $80 c, $0F c, $80 c, $3F c, $80 c, $7F c, $80 c,
    $7F c, $80 c, $3F c, $80 c, $0F c, $80 c, $03 c, $80 c,
    $01 c, $C0 c, $07 c, $C0 c, $1F c, $C0 c, $3F c, $C0 c,
    $3F c, $C0 c, $1F c, $C0 c, $07 c, $C0 c, $01 c, $C0 c,
    $00 c, $E0 c, $03 c, $E0 c, $0F c, $E0 c, $1F c, $E0 c,
    $1F c, $E0 c, $0F c, $E0 c, $03 c, $E0 c, $00 c, $E0 c,
    $00 c, $70 c, $01 c, $F0 c, $07 c, $F0 c, $0F c, $F0 c,
    $0F c, $F0 c, $07 c, $F0 c, $01 c, $F0 c, $00 c, $70 c,
    $00 c, $38 c, $00 c, $F8 c, $03 c, $F8 c, $07 c, $F8 c,
    $07 c, $F8 c, $03 c, $F8 c, $00 c, $F8 c, $00 c, $38 c,
    $00 c, $1C c, $00 c, $7C c, $01 c, $FC c, $03 c, $FC c,
    $03 c, $FC c, $01 c, $FC c, $00 c, $7C c, $00 c, $1C c,
    $00 c, $0E c, $00 c, $3E c, $00 c, $FE c, $01 c, $FE c,
    $01 c, $FE c, $00 c, $FE c, $00 c, $3E c, $00 c, $0E c,

create ship-body
    $FF c, $00 c, $FF c, $00 c, $FF c, $00 c, $E7 c, $00 c,
    $E7 c, $00 c, $FF c, $00 c, $FF c, $00 c, $FF c, $00 c,
    $7F c, $80 c, $7F c, $80 c, $7F c, $80 c, $73 c, $80 c,
    $73 c, $80 c, $7F c, $80 c, $7F c, $80 c, $7F c, $80 c,
    $3F c, $C0 c, $3F c, $C0 c, $3F c, $C0 c, $39 c, $C0 c,
    $39 c, $C0 c, $3F c, $C0 c, $3F c, $C0 c, $3F c, $C0 c,
    $1F c, $E0 c, $1F c, $E0 c, $1F c, $E0 c, $1C c, $E0 c,
    $1C c, $E0 c, $1F c, $E0 c, $1F c, $E0 c, $1F c, $E0 c,
    $0F c, $F0 c, $0F c, $F0 c, $0F c, $F0 c, $0E c, $70 c,
    $0E c, $70 c, $0F c, $F0 c, $0F c, $F0 c, $0F c, $F0 c,
    $07 c, $F8 c, $07 c, $F8 c, $07 c, $F8 c, $07 c, $38 c,
    $07 c, $38 c, $07 c, $F8 c, $07 c, $F8 c, $07 c, $F8 c,
    $03 c, $FC c, $03 c, $FC c, $03 c, $FC c, $03 c, $9C c,
    $03 c, $9C c, $03 c, $FC c, $03 c, $FC c, $03 c, $FC c,
    $01 c, $FE c, $01 c, $FE c, $01 c, $FE c, $01 c, $CE c,
    $01 c, $CE c, $01 c, $FE c, $01 c, $FE c, $01 c, $FE c,

create ship-tail
    $C0 c, $00 c, $E0 c, $00 c, $F8 c, $00 c, $FC c, $00 c,
    $FC c, $00 c, $F8 c, $00 c, $E0 c, $00 c, $C0 c, $00 c,
    $60 c, $00 c, $70 c, $00 c, $7C c, $00 c, $7E c, $00 c,
    $7E c, $00 c, $7C c, $00 c, $70 c, $00 c, $60 c, $00 c,
    $30 c, $00 c, $38 c, $00 c, $3E c, $00 c, $3F c, $00 c,
    $3F c, $00 c, $3E c, $00 c, $38 c, $00 c, $30 c, $00 c,
    $18 c, $00 c, $1C c, $00 c, $1F c, $00 c, $1F c, $80 c,
    $1F c, $80 c, $1F c, $00 c, $1C c, $00 c, $18 c, $00 c,
    $0C c, $00 c, $0E c, $00 c, $0F c, $80 c, $0F c, $C0 c,
    $0F c, $C0 c, $0F c, $80 c, $0E c, $00 c, $0C c, $00 c,
    $06 c, $00 c, $07 c, $00 c, $07 c, $C0 c, $07 c, $E0 c,
    $07 c, $E0 c, $07 c, $C0 c, $07 c, $00 c, $06 c, $00 c,
    $03 c, $00 c, $03 c, $80 c, $03 c, $E0 c, $03 c, $F0 c,
    $03 c, $F0 c, $03 c, $E0 c, $03 c, $80 c, $03 c, $00 c,
    $01 c, $80 c, $01 c, $C0 c, $01 c, $F0 c, $01 c, $F8 c,
    $01 c, $F8 c, $01 c, $F0 c, $01 c, $C0 c, $01 c, $80 c,

\ MULTI-BLIT table: 1-byte count, then quadruples (dx i8, dy i8, addr cell).
\ ' word , pushes the word's address at compile time and embeds it as a cell.
create ship-table
    3 c,
    0  c, 0 c, ' ship-nose ,
    8  c, 0 c, ' ship-body ,
    16 c, 0 c, ' ship-tail ,

\ -- Animation sprites: closed-eye smiley, ball, blank ----------------------
\ Closed-eye smiley (rows 2 and 4 are eyelids = $BD)
create smiley-closed-shifted
    $3C c, $00 c, $42 c, $00 c, $BD c, $00 c, $81 c, $00 c,
    $BD c, $00 c, $99 c, $00 c, $42 c, $00 c, $3C c, $00 c,
    $1E c, $00 c, $21 c, $00 c, $5E c, $80 c, $40 c, $80 c,
    $5E c, $80 c, $4C c, $80 c, $21 c, $00 c, $1E c, $00 c,
    $0F c, $00 c, $10 c, $80 c, $2F c, $40 c, $20 c, $40 c,
    $2F c, $40 c, $26 c, $40 c, $10 c, $80 c, $0F c, $00 c,
    $07 c, $80 c, $08 c, $40 c, $17 c, $A0 c, $10 c, $20 c,
    $17 c, $A0 c, $13 c, $20 c, $08 c, $40 c, $07 c, $80 c,
    $03 c, $C0 c, $04 c, $20 c, $0B c, $D0 c, $08 c, $10 c,
    $0B c, $D0 c, $09 c, $90 c, $04 c, $20 c, $03 c, $C0 c,
    $01 c, $E0 c, $02 c, $10 c, $05 c, $E8 c, $04 c, $08 c,
    $05 c, $E8 c, $04 c, $C8 c, $02 c, $10 c, $01 c, $E0 c,
    $00 c, $F0 c, $01 c, $08 c, $02 c, $F4 c, $02 c, $04 c,
    $02 c, $F4 c, $02 c, $64 c, $01 c, $08 c, $00 c, $F0 c,
    $00 c, $78 c, $00 c, $84 c, $01 c, $7A c, $01 c, $02 c,
    $01 c, $7A c, $01 c, $32 c, $00 c, $84 c, $00 c, $78 c,

\ Solid 8x8 ball, pre-shifted (for gravity-bouncer)
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

\ All-zeros pre-shifted block — used by actor-erase to wipe at any pixel x.
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

\ Frame tables: array of 16-bit pre-shifted-sprite addresses, one per frame.
create smiley-frames
    ' smiley-shifted ,
    ' smiley-closed-shifted ,

create flier-frames
    ' smiley-shifted ,

create ball-frames
    ' ball-shifted ,
