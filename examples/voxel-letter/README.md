# voxel-letter

A row of 1–5 ZX-Spectrum-font letters rendered as the front Z-layer of
an 8×8×8 voxel cube each, all rotating together around two axes under
keyboard control, at a steady 50 fps on a stock 3.5 MHz 48K.

## Controls

    7 / Q   pitch up
    6 / A   pitch down
    8 / O   yaw  left
    9 / P   yaw  right
    SPACE   quit

The 6/7/Q/A and 8/9/O/P pairs are alternates for the same axis.

## Quick start

    zt build  examples/voxel-letter/main.fs -o build/voxel.sna
    zt test   examples/voxel-letter/tests/        # 75 Forth tests
    pytest    examples/voxel-letter/tests/        # + 19 Python integration

Drop `build/voxel.sna` into FUSE or ZEsarUX. The default message is `FORTH`.

## Customising the message

In `main.fs`:

    create letters
        70 c,                          \ F
        79 c,                          \ O
        82 c,                          \ R
        84 c,                          \ T
        72 c,                          \ H

    5 constant letter-count
    11 constant letters-col-0          \ leftmost cell column

To centre N letters on the 32-column screen, set
`letters-col-0 = (32 - 2·N) / 2`.

| Letters | letters-col-0 | T/frame | fps |
|--------:|--------------:|--------:|----:|
|       1 |            15 |    24 K | **50** |
|       2 |            14 |    36 K | **50** |
|       3 |            13 |    47 K | **50** |
|       4 |            12 |    57 K | **50** |
|       5 |            11 |    67 K | **50** |

Numbers are full per-frame cost on real hardware: `render-frame +
poll-keys + quit?` for the dense `FORTH` glyphs.  The wait-frame cliff
at 70 K (one vsync) is the hard boundary — render must finish under
it to avoid waiting for the next interrupt.  All five letters land
under, with ~3.3 K headroom.

## Per-frame pipeline

    bake-rotation  ( yaw pitch -- )           \ once per frame
        bake-frame                             \ Forth: 2 multiplies
        bake-coords                            \ :::-Z80: fills x-cache + y-cache

    \ ── per letter ─────────────────────────────────────────────
    clear-buffer                               \ :::-Z80, 8 unrolled stores
    render-letter ( ch -- )                    \ :::-Z80, full row + col walk
    flush-letter ( cell-col cell-row -- )      \ single BLIT8

    \ ── input (once per frame) ──────────────────────────────────
    poll-keys                                  \ :::-Z80, 4 direct port reads
    quit?                                      \ :::-Z80, 1 direct port read

`bake-rotation` is shared across letters; everything else scales
linearly at ~10.4 K T per letter.

## How it works

**Geometry.** Each 8×8 ROM-font glyph occupies one z-layer of an 8×8×8
cube at cz = 0.  Voxels indexed by `(cx, cy)` at half-integer offsets
in `{-3.5, -2.5, …, +3.5}` — symmetric around origin so the rotated
projection always fits in 8 contiguous pixels.

**Projection.** For the cz = 0 slice, two-axis rotation reduces to:

    buffer_x = cx · cos(yaw)   + buf-half   ( buf-half = 3.5 )
    buffer_y = cy · cos(pitch) + buf-half

Exact when only one axis rotates; omits a small `cx · sin(yaw) ·
sin(pitch)` cross-term when both do — invisible at 1 px quantisation.

**Sine table.** 64 entries × 16-bit cells in 8.8 fixed.  Sized from
the corner-voxel quantisation: at `√3·3.5 ≈ 6.06` the radius, an
angular step Δθ moves the projection by 6.06·Δθ pixels.  64 entries
(5.625°/step, 0.59 px/step at the corner) is the sweet spot.

**The back-buffer.**  Plotting straight to screen forces the Spectrum
interleave-decode (~360 T per pixel even in `:::`).  Plotting into an
8-byte RAM buffer (one byte per scanline) makes byte-offset = `ry` and
mask = `mask_table[rx]` — a few instructions, ~50 T per pixel.  BLIT8
then overwrites a single 8×8 cell at hardware speed.  Crucially,
BLIT8's overwrite *is* the previous-frame clear — there's no separate
screen wipe.

**Mask LUT.**  `$80 >> (rx & 7)` was originally an `inc_b; jr cmp;
rrca; djnz` rotate (~105 T avg).  An 8-byte `mask-table` indexed by
`(rx & 7)` cuts it to ~55 T per plot.

**Coord caches.**  `bake-coords` (`:::` Z80) walks the per-frame
8.8-fixed accumulator 8 times per axis and writes the integer parts
into `x-cache` and `y-cache` (8 bytes each).  The hot inner loop reads
single bytes from these caches; no fixed-point math in the per-pixel
path.

**`:::` `render-letter`.**  The whole row + col walk lives in one
Z80 body.  At a high level:

    glyph_base = $3D00 + (ch - 32) * 8
    for row in 0..7:
        font_byte = mem[glyph_base + row]
        ry        = y-cache[row]                 ; in [0, 7]
        for col in 0..7:
            if font_byte bit 7 set:
                rx   = x-cache[col]              ; in [0, 7]
                mask = mask_table[rx & 7]
                letter-buf[ry] |= mask
            font_byte <<= 1

In Z80 the col walk is `SLA C; JR NC, skip; …plot…; skip: INC HL; DJNZ
cloop`.  The outer row counter is parked on the stack across the inner
DJNZ.

**IM 2 ISR.**  The simulator has no ROM at $0038, so IM 1 interrupts
would run into uninitialised memory.  We install a no-op IM 2 handler
at startup so `wait-frame` (`ei + halt + di`) is safe.  On real
hardware a ROM-based IM 1 handler would do the job.

## Optimisation history

| Stage                                                | T/frame (1 letter) | fps |
|------------------------------------------------------|-----------------:|----:|
| Pure-Forth plot, full-screen clear                   | 406 K | 8.6 |
| `:::` plot, full-screen clear                        | 367 K | 9.5 |
| `:::` plot, no clear                                 | 220 K |  16 |
| + `::` inline of inner-loop helpers                  | 160 K |  22 |
| + back-buffer + BLIT8 (no Spectrum interleave plot)  |  77 K |  46 |
| + `:::` `bake-coords`, `:::` inner col walk          |  52 K |  50 |
| + `:::` `render-letter` (folds row loop into Z80)    |  32 K |  50 |
| + mask LUT in inner col walk                         |  29 K |  50 |
| + 8-byte buffer, single BLIT8, no quadrant math      |  23 K |  50 |
| + `:::` `poll-keys` (direct port reads)              |  24 K |  50 |
| + drop mask-LUT carry handling                       |  24 K |  50 |
| + `:::` `clear-buffer` (unrolled stores)             |  24 K |  50 |

The walk took us from a 406 K T-state frame to a 24 K T-state
*full-loop-body* frame for 1 letter — a **17× speedup** with the same
algorithm — and scaled the `n=5 @ 50 fps` ceiling from impossible to
comfortable.  Every step moved the `:::`-Z80 boundary upward by one
layer of dispatch, or shaved a per-pixel constant.

The last three rows tell the story of a misleading benchmark: the bulk
optimizations hit a "5 letters @ 50 fps" claim that excluded
`poll-keys` + `quit?`.  With those included on dense glyphs (`FORTH`),
the demo was actually 25 fps until the input path went `:::` and the
mask LUT shed its carry handling.

## Tuning

`angle-step` in `main.fs` (default 1) controls how many sine-table
steps a held key advances per frame.  At 50 fps with step=1 a held key
rotates ~280°/sec.

## Files

    main.fs                    -- frame loop, message string, IM 2 setup
    lib/sin64.fs               -- 64-entry signed sine table (8.8 fixed)
    lib/voxel.fs               -- bake-frame: per-frame basis baking
    lib/coord_cache.fs         -- 8-byte x-cache + y-cache buffers
    lib/buffer.fs              -- 8-byte back-buffer + mask-table + :::-clear/plot/flush
    lib/render.fs              -- :::-Z80 bake-coords + render-letter
    lib/pixel_addr.fs          -- Spectrum byte-address arithmetic
    lib/plot.fs                -- pure-Forth plot (reference, unused)
    lib/plot_native.fs         -- :::-Z80 screen plot (reference, unused)
    lib/input_voxel.fs         -- :::-Z80 poll-keys + quit?, direct port reads

    tests/test_sin64.fs            -- 15 tests: angles, wrap, Pythagorean
    tests/test_voxel.fs            -- 12 tests: bake-frame outputs, walk
    tests/test_buffer.fs           --  7 tests: plot-buf, clear-buffer
    tests/test_plot.fs             -- 16 tests: pure-Forth address + bit
    tests/test_plot_native.fs      --  9 tests: :::-Z80 screen plot
    tests/test_render.fs           --  4 tests: end-to-end render output
    tests/test_input.fs            --  5 tests: no-keys quit?, stack preservation
    tests/test_main_integration.py -- 19 tests: Python end-to-end with
                                      simulated key presses

    tests/gen_sine.py          -- table generator (Python, host-side)

## A note on mask-table placement

`mask-table` is an 8-byte LUT in `buffer.fs` indexed by `rx & 7` for
the bit mask.  The inner col walk skips high-byte carry handling on
`mask-table-low + (rx & 7)` because the table currently lands at low
byte `0x1b`, and `0x1b + 7 = 0x22` never carries.  If future edits
shift the table past low byte `0xF8`, `test-far-corner-last-byte-last-bit`
(in `test_buffer.fs`) will fail and you'll need to either (a) restore
the carry handling or (b) hand-place the table at an aligned address.
