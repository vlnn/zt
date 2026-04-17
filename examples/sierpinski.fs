\ sierpinski.fs — Sierpinski triangle on the ZX Spectrum attribute area
\
\ Uses the property that (col AND row) == 0 produces a fractal
\ pattern when plotted as a grid. Each matching cell gets attribute
\ value 56 (bright white ink on black paper), others get 0 (invisible).
\
\ The Spectrum attribute area starts at address 22528 ($5800),
\ with 32 columns x 24 rows = 768 bytes.

: sierpinski  ( -- )
    24 0 do
        32 0 do
            i j and 0= if 56 else 0 then
            j 32 * i + 22528 + c!
        loop
    loop ;

: main  sierpinski begin again ;
