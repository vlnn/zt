# Plasma demo

A scrolling colour plasma painted into the Spectrum's attribute area at
`$5800–$5AFF`. `plasma-init` paints the buffer once; the foreground loop
reads QAOP / 6789 keys every frame and pans the buffer with `scroll-attr`.
The plasma is never redrawn — you're looking at a static buffer being
panned around by the player.

The largest bundled example, exercising most of the compiler pipeline:
multi-file includes with path deduplication, attribute-memory manipulation,
a precomputed phase buffer, per-frame timing, and keyboard input via
`KEY-STATE`.

## Run

Load `plasma.sna` in Fuse, ZEsarUX, or any 48K-compatible Spectrum
emulator. There's also a demo video in the project's main
[README](../../README.md#demo).

Controls (either set works — the keyword is OR-folded):

| Direction | Keys             |
|-----------|------------------|
| up        | `Q` or `9`       |
| down      | `A` or `8`       |
| left      | `O` or `6`       |
| right     | `P` or `7`       |

## Source layout

```
plasma4/
├── main.fs                    ← entry point; require app/plasma.fs
├── lib/
│   ├── math.fs                ← : mod32 ( n -- n%32 ) 31 and ;
│   ├── screen.fs              ← attrs, row-addr, attr-addr, attr!
│   └── timing.fs              ← ms-per-frame, frames>ms
└── app/
    └── plasma.fs              ← wave table, phased buffer, draw, animate
```

Both `plasma.fs` and `screen.fs` `require math.fs`, but the file is loaded
only once: `REQUIRE` canonicalises paths and dedups, so the include graph
is a DAG rather than a tree.

## The code

```forth
create wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  \ ... 32 entries total, triangle wave

variable phase
create phased 32 allot

: wave@       ( i -- n )        mod32 wave + c@ ;
: phased@     ( i -- n )        phased + c@ ;
: paper-attr  ( paper -- attr ) 3 lshift 64 or ;

: rephase  ( -- )
    scr-cols 0 do
        i phase @ + wave@
        phased i + c!
    loop ;

: draw-row  ( row -- )
    dup phased@
    swap row-addr
    scr-cols 0 do
        over i phased@ xor
        paper-attr
        over c!  1+
    loop
    2drop ;

: draw          ( -- )  rephase  scr-rows 0 do i draw-row loop ;
: plasma-init   ( -- )  0 phase !  draw ;

\ QAOP / 6789 bindings read via KEY-STATE
: dx            ( -- n )  right? left? - ;
: dy            ( -- n )  down?  up?   - ;
: react         ( -- )    dx dy scroll-attr ;

: animate       ( -- )
    plasma-init
    begin wait-frame react again ;
```

Every identifier here is a Forth word — no syntax, no types, just a
stream of words pushing and popping a parameter stack. `:` starts a
definition, `;` ends it. `( ... )` is a stack-effect comment and produces
no code. `create wave` followed by `c,` builds an inline byte array;
`allot` reserves raw bytes for `phased` without initialising them.

## The phase-buffer trick

The trick is `phased`: rather than calling `wave@` twice per cell
(32 × 24 = 768 cells × 2 lookups per frame), the 32 column-phase values
are computed once into a small RAM buffer by `rephase`, and each row
XORs against that buffer column-by-column. Halves the table traffic
inside the hot loop, which matters on a 3.5 MHz Z80.

The `animate` loop is unusual: `plasma-init` paints the attribute area
once, and then the frame loop is just `wait-frame react`. `react` reads
the QAOP and 6789 keys via `KEY-STATE`, derives a `dx dy` direction, and
calls `scroll-attr` to shift the attribute buffer that much.

## Build

```
zt build examples/plasma4/main.fs -o build/plasma.sna --map build/plasma.map
```

You get a `.sna` that boots straight into the plasma drawn across the
attribute area at `$5800–$5AFF`, then responds to QAOP / 6789 keys to pan it.

## Tests

`tests/test_wave.fs` is a Forth unit test on the wave-table indexing.
Pytest picks it up via the project's root `conftest.py`:

```
pytest examples/plasma4/tests/
```
