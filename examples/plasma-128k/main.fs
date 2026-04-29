\ examples/plasma-128k/main.fs
\
\ Double-buffered plasma using the 128K shadow screen.
\
\ Bank 5 ($4000) and bank 7 (accessible at $C000 when paged in) each hold
\ a full Spectrum screen. Bit 3 of port $7FFD chooses which the ULA reads.
\
\ Protocol:
\   - Bank 7 is paged into slot 3 for the whole program, so we can always
\     write to either screen: $5800 hits bank 5's attrs, $D800 hits bank 7's.
\   - shadow-visible? tracks which buffer the ULA is currently showing.
\     We ALWAYS write to the hidden buffer — never touch the visible one.
\   - When draw-plasma finishes, flip bit 3: hidden becomes visible. Atomic,
\     zero-copy, no tearing even if draw-plasma took multiple ULA frames.
\
\ Port values (bank 7 always in slot 3, bit 4 = 0 = Pentagon BASIC ROM):
\   $07 — normal visible
\   $0F — shadow visible

require ./lib/math.fs

$07 constant page-normal-visible
$0F constant page-shadow-visible

$5800 constant normal-attrs
$D800 constant shadow-attrs

32    constant scr-cols
24    constant scr-rows

\ Lookup table turning a 0..31 index into a 0..7 triangle wave.
create wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,

variable phase
variable shadow-visible?     \ 0 = ULA on normal screen, nonzero = on shadow

\ sample the triangle wave at index i (mod 32)
: wave@  ( i -- n )  mod32 wave + c@ ;

\ Plasma cell colour: XOR of two wave values → 0..7, placed into the paper
\ bits of the attribute byte. Bit 6 = bright. Ink = 0 = black. Pixels are
\ not touched (they stay 0), so each cell shows solid paper colour.
: plasma-attr  ( col row -- attr )
    phase @ + wave@                ( col wave-col )
    swap phase @ + wave@           ( wave-col wave-row )
    xor                            ( 0..7 )
    3 lshift                       ( paper-bits )
    $40 or ;                       \ bright bit

\ linear offset within an attribute area for cell (col, row)
: attr-offset  ( col row -- offset )  scr-cols * + ;

\ base address of the attribute area for whichever screen is currently hidden
: hidden-attrs  ( -- attrs-base )
    shadow-visible? @ if normal-attrs else shadow-attrs then ;

\ render one full plasma frame into the hidden buffer
: draw-plasma  ( -- )
    hidden-attrs                            ( base )
    scr-rows 0 do
        scr-cols 0 do
            i j plasma-attr                 ( base attr )
            over i j attr-offset + c!       ( base )
        loop
    loop
    drop ;

\ swap visible and hidden buffers via $7FFD bit 3
: flip  ( -- )
    shadow-visible? @ if
        page-normal-visible raw-bank!
        0 shadow-visible? !
    else
        page-shadow-visible raw-bank!
        1 shadow-visible? !
    then ;

\ advance the phase by one frame
: step  ( -- )  1 phase +! ;

\ entry point: page bank 7 into slot 3 and run the draw/flip/step loop
: main
    7 bank!                    \ bank 7 into slot 3, stays there for ever
    0 shadow-visible? !        \ ULA currently on normal (matches $7FFD = $07)
    0 phase !
    begin
        draw-plasma            \ fully populate the hidden buffer
        flip                   \ one OUT; bit 3 toggles, ULA swaps buffers
        step
    again ;

