\ examples/shadow-flip/main.fs
\
\ Static two-picture shadow-screen test with a "did code run?" marker.
\
\ Bank 5 is pre-seeded with a green diagonal pattern at build time. If you
\ see that pattern frozen, my runtime code isn't executing. If you see
\ bright white, runtime code ran and overwrote bank 5. Then it alternates
\ with shadow-screen (flashing red) every second.

\ Pre-paint the entire bank 5 screen at build time.
\ If you see BRIGHT GREEN everywhere, runtime code did not execute.
\ If you see SOLID WHITE, runtime paint-normal successfully overwrote bank 5.
\ Alternating with SHADOW (bank 7), which is painted at runtime only.

\ Pre-seed bank 5 with a visible top-row marker:
\   pixels: 32 bytes of $FF at offset 0 = top pixel row across all 32 cols
\   attrs:  32 bytes of $44 at offset 6144 = top attribute row, green-on-black
\ If this is visible, snapshot loading works. If code also runs, paint-normal
\ overwrites it with bright white everywhere.

5 in-bank
  create seed-pixels
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
    $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c, $FF c,
  \ gap: jump from offset 32 to offset 6144 → 6112 bytes of zero padding
  6112 allot
  create seed-attrs
    $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c,
    $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c,
    $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c,
    $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c, $44 c,
end-bank

\ Paint the whole bank-5 screen area by just filling via the words below;
\ the 8 bytes of seed-bitmap above already go into the first row of the
\ pixel area, so if code doesn't run you see a striped green top line.

$4000 constant normal-bitmap
$5800 constant normal-attrs
$C000 constant shadow-bitmap
$D800 constant shadow-attrs

6144 constant bitmap-size
768  constant attrs-size

$07 constant page-normal-visible
$0F constant page-shadow-visible

: paint-solid  ( bitmap-addr attrs-addr attr-byte -- )
    >r
    attrs-size r> fill
    bitmap-size 0 fill ;

: paint-normal  ( -- )
    \ $78 = bright-white paper, black ink; pixels 0 → solid white
    normal-bitmap normal-attrs $78 paint-solid ;

: paint-shadow  ( -- )
    \ $50 = bright-red paper, black ink; pixels 0 → solid red
    shadow-bitmap shadow-attrs $50 paint-solid ;

: show-normal  ( -- )  page-normal-visible raw-bank! ;
: show-shadow  ( -- )  page-shadow-visible raw-bank! ;

variable dummy
: delay-tick  ( -- )  dummy @ 1 + dummy ! ;
: wait-one-second  ( -- )
    10000 0 do  delay-tick  loop ;

: main
    7 bank!
    paint-normal
    paint-shadow
    begin
        show-normal
        wait-one-second
        show-shadow
        wait-one-second
    again ;
