# zt — FORTH roadmap for game creation

This document proposes primitives to add to `PRIMITIVES` (and their
stdlib/Forth-level companions) to make zt practical for the four game shapes
that matter: **text adventure**, **puzzle / board**, **action / arcade**, and
**demo / effects**.

Primitives are organized by capability, not by genre, because most belong to
more than one. Each entry lists its stack effect, proposed depth, and which
genres it unblocks. Graceful-degradation notes call out how a 48K build
should behave when a primitive assumes hardware only a 128K has.

Conventions:
- **Spec** primitives are described by their stack effect, rationale, and a
  one-liner Forth usage example.
- **Deep** primitives include a Z80 register-plan sketch and, where novel,
  an opcode outline.
- Cell-width is 16-bit throughout (zt's only cell size).

---

## 1. Timing and frame synchronization

The single most missing capability. Every genre needs it: text adventures for
cursor blink, puzzles for animations between moves, arcade for consistent
speed, demo for effects.

### `WAIT-FRAME ( -- )` — deep  *(shipped)*

Shipped. `create_wait_frame` in `assemble/primitives.py` issues `EI; HALT; DI`
and resumes on the next 50 Hz frame interrupt. After it returns, the program
has ~19,968 T-states (about 4,000 dispatches) before the next interrupt.

Works unchanged with either the ROM's IM 1 (default) or a user-installed IM 2
handler — see §8.1, also shipped. Programs that need to drive AY music or
synchronise effects from the interrupt install an `IM2-HANDLER!` and keep
calling `wait-frame` exactly as before.

*Genres:* all.

### `TICKS ( -- n )` — spec

Return `_frame_counter`. Wraps at 65536 frames (~22 minutes).

```forth
: benchmark  ticks my-word ticks swap - . cr ;
```

*Genres:* all.

### `TICKS! ( n -- )` — spec

Set the counter. Mostly useful for resetting before a benchmark or checkpointing in a game.

### `PAUSE ( frames -- )` — spec

```forth
: pause  ( frames -- )  0 do wait-frame loop ;
```

Pure Forth; no new primitive needed once `WAIT-FRAME` exists. Used in
`examples/reaction/app/reaction.fs` and `examples/mined-out/app/hud.fs`
under the local name `throttle` / `pause`.

*Genres:* all.

---

## 2. Random numbers

Every genre wants randomness: dungeon layout (adventure), shuffling (puzzle),
enemy AI (arcade), dithering/noise (demo).

### `rnd ( -- n )` — *(stdlib shipped, native primitive still open)*

Shipped at the Forth level in `src/zt/stdlib/rand.fs` as a 16-bit linear
congruential generator: `seed' = seed * 25173 + 13849`. Adequate for game
randomness; ~80 T-states per call dominated by the `*` primitive.

```forth
: rnd     ( -- n )         rnd-seed @ 25173 * 13849 + dup rnd-seed ! ;
```

The faster Xorshift-style native primitive originally proposed below is
still open. Useful where the LCG cost shows up in a profile.

```
RND:    push hl
        ld   hl, (_rnd_seed)
        ld   a, h
        rra
        ld   a, l
        rra
        xor  h
        ld   h, a
        ld   a, l
        rra
        ld   a, h
        rra
        xor  l
        xor  h
        ld   l, a
        ld   (_rnd_seed), hl
        jp   NEXT
```

(This is a standard Z80 Xorshift-like PRNG — ~40 T-states per call. Half
the cost of the LCG.)

*Genres:* all.

### `seed! ( n -- )` — *(stdlib shipped)*

Shipped. `: seed!  ( n -- )  rnd-seed ! ;` in `src/zt/stdlib/rand.fs`. Idiomatic
Forth setter naming (bang on the end). Needed for reproducible puzzle
layouts and replay debugging.

### `random ( n -- 0..n-1 )` — *(stdlib shipped)*

Shipped. `: random  ( n -- 0..n-1 )  rnd swap u/mod drop ;` in
`src/zt/stdlib/rand.fs`. Not quite uniform for non-power-of-two `n` (the
modulo bias on a 16-bit input is small enough that no game cares), but
good enough for everything in the bundled examples.

`stdlib/rand.fs` also ships `between ( lo hi -- n )` for picking a random
value in a closed interval.

*Genres:* puzzle, arcade, demo.

---

## 3. Input

### 3.1 Fix `KEY` and `KEY?` (real-hardware fix)  *(shipped)*

Shipped. `create_key` and `create_key_query` now scan port `$FE`
directly. `KEY` blocks until any key is down and returns its ASCII
code; `KEY?` returns a non-blocking flag.

### 3.2 `KEY-STATE ( c -- flag )` — deep  *(shipped)*

Shipped. `create_key_state` in `assemble/primitives.py` looks up the
ASCII code in the `_key_table` and tests the corresponding bit on
port `$FE`. Returns `-1` if held, `0` otherwise.

The companion stdlib (`src/zt/stdlib/input.fs`) provides a higher-level
binding API:

```forth
\ Bind direction keys (each as an ASCII code), then test:
54 55 56 57 set-keys!     \ ASCII '6' '7' '8' '9' = L R U D
: tick
  wait-frame
  key-left?  if player-left  then
  key-right? if player-right then ;
```

`pressed? ( keycode -- 0|1 )` is the underlying single-key test if you
prefer to call `key-state` directly without binding.

*Genres:* arcade (essential), demo (user controls), puzzle (keyboard nav).

### 3.3 Kempston joystick — `KEMPSTON ( -- bits )` — medium

Read port `$1F`. Returns a byte with bits 0–4 for right / left / down / up /
fire. Five instructions.

```forth
: joy-fire?  ( -- flag )  kempston 16 and 0<> ;
: joy-left?  ( -- flag )  kempston 2 and 0<>  ;
```

Kempston is both the most common and the easiest-to-implement joystick
interface on the Spectrum, which is why every arcade game supports it.

*Genres:* arcade (common peripheral), not relevant for others.

### 3.4 `ACCEPT ( addr maxlen -- len )` — deep

Read a line of text into a buffer. The canonical Forth input primitive, essential for text adventures.

```
ACCEPT: ( addr max -- len )
        pop  de                 ; de = addr (was second)
        ld   b, l               ; b = max (TOS low byte)
        ld   c, 0               ; c = count so far
.loop:  call _wait_key          ; reuses KEY minus the dispatch
        cp   13                 ; ENTER?
        jr   z, .done
        cp   8                  ; backspace?
        jr   z, .backspace
        cp   32                 ; non-printable?
        jr   c, .loop
        ld   (de), a
        inc  de
        inc  c
        ld   a, c
        cp   b
        jr   nc, .done          ; buffer full
        ; echo the character
        push bc : push de
        ld   l, a : ld h, 0
        call _emit_char_core
        pop  de : pop bc
        jr   .loop
.backspace: ; handle if c > 0
        ...
.done:  ld   l, c
        ld   h, 0
        ; push HL as new TOS
        push hl
        pop  hl
        jp   NEXT
```

Returns the number of bytes read. Typical usage:

```forth
create buf 80 allot
: prompt  ." > " buf 80 accept buf swap ;
```

*Genres:* text adventure (essential).

### 3.5 `WORD ( delimiter -- addr len )` — medium

Parse the next whitespace-delimited token from the current input buffer. The
text-adventure parser relies on this.

```forth
: parse-verb  ( -- )
    buf 80 accept drop
    32 word upper-case       \ first word uppercased
    dup verb-go       compare 0= if do-go exit then
    dup verb-take     compare 0= if do-take exit then
    ... ;
```

*Genres:* text adventure.

---

## 4. Graphics — pixel and screen helpers

Realistically, every dynamic game will use it's custom made graphical engine. These words are general and should be used only for prototyping if at all.

### 4.1 `SCREEN-ADDR ( row col -- addr )` — medium

Given an 8-pixel character cell position, return the address of its top
scanline in the Spectrum's interleaved screen memory layout. This is the
plumbing underneath every other graphics primitive.

```
SCREEN-ADDR: ( row col -- addr )
        ; HL = col (0..31)
        ld   a, l
        ld   e, a               ; E = col (assume 0..31)
        pop  hl                 ; HL = row (0..23)
        ; Spectrum layout: addr = $4000 | (band << 11) | (line << 8) | (trow << 5) | col
        ld   a, l               ; A = row
        and  $18                ; band << 3
        or   $40
        ld   d, a               ; D = high byte
        ld   a, l
        and  $07                ; trow (low 3 bits of row)
        rrca : rrca : rrca      ; trow << 5
        or   e
        ld   e, a               ; E = low byte = (trow << 5) | col
        ex   de, hl
        jp   NEXT
```

*Genres:* all that use graphics.

### 4.2 `PLOT ( x y -- )` — deep

Set a single pixel. `x` is 0–255, `y` is 0–191.

```
PLOT:   ; y in HL-high-byte-ignored / y in L (assume 0..191), x on stack
        ; Stack: ( x y -- ) with y=TOS
        ld   a, l               ; A = y
        pop  hl                 ; HL = x
        ; compute screen addr from (x, y): same interleave as SCREEN-ADDR
        ; but at the scanline level, not character level
        ld   b, a               ; B = y
        and  $07
        rlca : rlca : rlca
        or   l                  ; A = x bits 5..7 clear combined with (y & 7) << 3? — flesh out
        ...
        ld   a, l
        and  $07
        ld   b, a
        inc  b
        ld   a, $80
.shift: rrca
        djnz .shift
        or   (hl)
        ld   (hl), a
        pop  hl                 ; restore TOS
        jp   NEXT
```

Full Bresenham-style line plotting builds on this; see 4.4.

*Genres:* all that use graphics — demo especially.

### 4.3 `UNPLOT ( x y -- )`, `XPLOT ( x y -- )` — spec

Variants of `PLOT`: clear the bit, XOR the bit. XOR is especially useful for
drawing and erasing sprites.

### 4.4 `LINE ( x1 y1 x2 y2 -- )` — deep

Bresenham's line algorithm. ~60 lines of Z80. The single most useful high-level graphics primitive because it enables polygon drawing, UI borders, wireframe 3D.

Alternative: implement `LINE` in Forth using `PLOT`. Much slower (~100
dispatches per pixel) but one-evening job. For a demo-effects target it
should be native.

*Genres:* demo, puzzle (UI).

### 4.5 Attribute composition — *(stdlib shipped)*

zt's chosen model is **attribute combinators**, not stateful "current
attribute" setters. Build an attribute byte by composing pieces, then
write it explicitly via `attr!` or `fill-attrs`. State stays out of the
graphics path, which makes scroll/restore patterns straightforward.

Shipped in `src/zt/stdlib/screen.fs`:

```forth
: colour      ( ink paper -- byte ) 3 lshift or ;       \ pack ink + paper
: bright      ( byte -- byte' )     64 or ;             \ set bright bit
: flashing    ( byte -- byte' )     128 or ;            \ set flash bit
: attr!       ( byte col row -- )   attr-addr c! ;
: attr@       ( col row -- byte )   attr-addr c@ ;
: fill-attrs  ( byte -- )           attrs 768 rot fill ;
: row-attrs!  ( byte row -- )       scr-cols * attrs +  scr-cols  rot fill ;
```

Idiomatic usage:

```forth
: red-on-black-bright  2 0 colour bright ;
: paint-cell  ( col row -- )  red-on-black-bright -rot attr! ;
```

The attribute base address (`$5800`), screen dimensions (`scr-cols`,
`scr-rows`), and the `attr-addr` cell-address helper are all exposed
as constants/words from the same file.

*Genres:* all that use graphics.

### 4.6 `AT-XY ( col row -- )` — spec  *(shipped)*

Shipped. `create_at_xy` moves the `EMIT` cursor to any text-cell
position (0–31 columns, 0–23 rows on a 48K screen). Pairs with the
already-shipped `reset-cursor`.

*Genres:* all.

---

## 5. Graphics — sprites

The seven SP-stream sprite primitives shipped in
[`assemble/sprite_primitives.py`](../src/zt/assemble/sprite_primitives.py)
cover much of the original wishlist below: `BLIT8`, `BLIT8C`, `BLIT8X`,
`BLIT8XC`, `MULTI-BLIT`, plus the `LOCK-SPRITES`/`UNLOCK-SPRITES` DI
wrappers. See `docs/primitives.md` and `examples/sprite-demo/`. The
remaining items — XOR-blit, pre-shift table generator, full-screen
pixel scroll — are still open and described below.

### 5.1 `XOR-SPRITE ( addr col row -- )` — *(partially shipped — copy variants only)*

Pixel- and char-aligned blits shipped under different names. `BLIT8X
( shifted-src x y -- )` is the pixel-aligned 8×8 monochrome blit;
`BLIT8XC` is the colored variant. Char-aligned versions (`BLIT8`,
`BLIT8C`) cover the simpler 8-aligned case at lower cost. The shipped
primitives do plain *copy*, not XOR — so erase-by-redraw isn't free
yet. A true XOR-blit primitive (the historic Spectrum idiom for cheap
sprite erase) is still a candidate addition; the original proposal
below sketches the Z80 path.

```
; sprite bytes at (addr): H bytes, one per scanline.
; (col, row) in character coordinates (8-aligned)
XOR-SPRITE:
        ; setup: HL = addr (TOS), DE = col+row
        pop  de                 ; row | (col in E, row in D)
        ; compute screen address from (col, row) using SCREEN-ADDR logic
        ; then loop H times: xor sprite byte into screen
        ld   b, SPRITE_H
.row:   ld   a, (hl)
        ex   de, hl
        xor  (hl)
        ld   (hl), a
        ex   de, hl
        inc  hl
        ; advance DE to next scanline (complicated by Spectrum layout)
        call _next_scanline
        djnz .row
        jp   NEXT
```

Critical detail: "next scanline" on a Spectrum requires either a precomputed
table or a three-step check on the scanline counter. The common trick is a
256-entry lookup table built at compile time.

An alternative signature `XOR-SPRITE ( addr x y w h -- )` allows
pixel-aligned sprites but costs per-row bit shifts. Byte-aligned is 4× faster;
many arcade games live with character-grid movement for that reason.

*Genres:* arcade (essential).

### 5.2 `PRE-SHIFT ( src dst -- )` — deep *(consumer shipped, generator still open)*

The shipped `BLIT8X`/`BLIT8XC` primitives expect a pre-shifted source
laid out as 8 sequential 8-byte tables (one per shift offset 0..7).
What's still open is the *generator* — a primitive (or build-time
directive) that takes a single 8-byte sprite and emits the eight
shifted copies. Today the caller prepares those copies by hand or in
host-side Python before embedding them with `c,`. A `PRE-SHIFT`
primitive would let users skip the manual table.

Pre-compute eight shifted copies of a sprite for pixel-accurate blitting
without per-frame shifting. Classic arcade optimization.

Usage:
```forth
create alien-sprite  ... allot
create alien-shifts  256 allot   \ 8 shifts × 32 bytes
: init-sprites  alien-sprite alien-shifts pre-shift ;
```

At runtime, `SPRITE ( x y -- )` picks which pre-shifted copy to blit based
on `x AND 7`.

*Genres:* arcade.

### 5.3 `SCROLL-LEFT ( -- )`, `SCROLL-UP ( -- )` — medium

Full-screen 8-pixel pixel scroll. Roughly 200 lines of `LDIR` or unrolled
sequences. Expensive but sometimes essential (scrolling platformer, demo
effects).

```forth
: scroll-frame  wait-frame scroll-left ;
```

Graceful degradation: on 48K, full-screen scroll is too slow for 50fps. Ship
`PARTIAL-SCROLL ( top-row rows -- )` that scrolls only a band of the screen.

Note the *attribute*-level scroll is already shipped: `SCROLL-ATTR ( dx dy -- )`
shifts the 32×24 attribute page by `(dx, dy)` with row/column wrap. Used by
the plasma demo (`examples/plasma4/`) to pan a precomputed colour buffer
under keyboard control. Different operation than the pixel scroll above,
but covers many demo use cases on its own.

*Genres:* arcade, demo.

### 5.4 `grid@ ( col row -- v )`, `grid! ( v col row -- )` — *(stdlib shipped)*

Shipped under different names than the original `TILE@`/`TILE!` proposal.
`src/zt/stdlib/grid.fs` provides a bind-once tile-map abstraction:

```forth
require grid.fs

create board  704 allot               \ 32 * 22 bytes
board 32 22 grid-set!                 \ bind addr + dimensions
0 grid-clear                          \ wipe to byte 0
1 5 3 grid!                           \ store 1 at (col=5, row=3)
4 2 grid@ .                           \ fetch byte at (4, 2)
```

Plus `grid-area`, `grid-row-addr`, `fill-row`, `fill-col`, `in-bounds?`,
and 4-/8-connected neighbour counts (`neighbours4`, `neighbours8`).
Exercised by the bundled Tetris, Mined Out, and Arkanoid examples.

The bind-once shape is more compact at call sites than passing the map
address every time; the cost is one global "current grid" register.

*Genres:* puzzle, arcade.

### 5.5 Double-buffered attribute area — spec-level pattern

Pure Forth idiom, not a primitive. Allocate a shadow buffer at, say,
`$C000`, write all per-frame attribute updates there, then `CMOVE` to
`$5800` during `WAIT-FRAME`.

```forth
create shadow-attr 768 allot
: flush-attrs  shadow-attr $5800 768 cmove ;
: draw-frame   shadow-attr clear-shadow compose-frame wait-frame flush-attrs ;
```

The existing `CMOVE` primitive is good enough; this is an idiom worth
documenting, not a primitive worth adding.

*Genres:* arcade (eliminates flicker), demo.

---

## 6. Audio

### 6.1 `BEEP ( cycles period -- )` — deep (48K)  *(shipped)*

Shipped. `create_beep` in `assemble/primitives.py` toggles bit 4 of
port `$FE` at a cycle-counted interval. `cycles` is the number of
half-period iterations, `period` is the half-period in T-states.

User-friendly wrappers in [`stdlib/sound.fs`](../src/zt/stdlib/sound.fs):
`click`, `chirp`, `low-beep`, `high-beep`, `tone`.

Not polyphonic; game logic freezes during the tone. Adequate for sound
effects (short blips). For music, see §6.3 (AY) below.

*Genres:* arcade, puzzle (feedback clicks), demo.

### 6.2 `click ( -- )` — *(stdlib shipped)*

Shipped via BEEP, not via the border port. `: click  1 100 beep ;` in
`src/zt/stdlib/sound.fs`. The original proposal was a raw border-toggle
two-write idiom (`16 border 7 border`), but going through BEEP gives a
cycle-counted half-wave — audible on real hardware and trivially
extensible to `chirp`, `low-beep`, `high-beep`, `tone`, all of which
also ship in the same file.

*Genres:* all.

### 6.3 AY register access — *(stdlib shipped)*

Equivalent shipped. Rather than the originally proposed `AY!` /
`AY@` primitives, the same surface lives at the stdlib layer in
`src/zt/stdlib/ay.fs`:

```forth
::: ay-set  ( val reg -- )         \ low-level register write
$FFFD/$BFFD canonical out pair
                                   \ wrappers
: ay-mixer!   ( bits   -- )        \ R7
: ay-noise!   ( period -- )        \ R6 (5-bit)
: ay-tone-a!  ( period -- )        \ R0/R1 (12-bit)
: ay-tone-b!  ( period -- )        \ R2/R3
: ay-tone-c!  ( period -- )        \ R4/R5
: ay-vol-a!   ( level  -- )        \ R8 (4-bit)
: ay-vol-b!   ( level  -- )        \ R9
: ay-vol-c!   ( level  -- )        \ R10
                                   \ constants
ay-mixer-tones-only                \ $38 — tones on, noise/IO off
ay-volume-max                      \ $0F
ay-volume-mute                     \ 0
```

48K graceful-degradation: writes to ports `$FFFD`/`$BFFD` are floating-bus
on 48K — silent but harmless, no detection ceremony required.

Working music examples: `examples/im2-music/` (frame-locked C-major
arpeggio) and `examples/im2-bach/` (Bach Invention 4 transcribed
from LilyPond).

### 6.4 Tracker-style driver — architectural, not primitive

A 128K AY driver runs from the interrupt handler, reads a tune format each
frame, updates AY registers. Out of scope for "primitives" but worth
mentioning because its existence determines what data format the primitives
should expose.

`examples/im2-bach/` is a working two-voice reference shape: the score is
a flat array of 16-bit period pairs (one per 16th note), the IM 2 ISR
walks one step every eight frames, `play-or-mute-{a,b}` writes period and
volume on each tick. Promoting this into a stdlib-factored driver with a
documented score format is the open work; the example shows what the
shape can look like.

---

## 7. Text adventure support

Most text-adventure needs are met by `ACCEPT`, `WORD`, `EMIT`, `TYPE`, and
`COMPARE`. A few more would help.

### 7.1 `COMPARE ( addr1 len1 addr2 len2 -- flag )` — deep

Lexicographic string compare. Returns -1 / 0 / 1 (Forth convention uses 0 for
equal, ±1 for ordering). Needed for case-insensitive verb matching.

```forth
: verb?  ( addr len -- flag )
    s" GO" compare 0= ;
```

Around 30 lines of Z80 — mostly bounds checks and a `CPIR`-style loop.

*Genres:* text adventure.

### 7.2 `UPPER ( c -- C )`, `>UPPER ( addr len -- )` — spec

Character and in-place string uppercasing. Two lines and ten lines of Z80
respectively. Essential for case-insensitive command parsing.

### 7.3 `SAVE-SLOT ( slot -- ok )`, `LOAD-SLOT ( slot -- ok )` — medium

Save/restore a fixed-size game state to/from divMMC or a named RAM location.
On 48K with no storage device, fall back to printing the state as hex for
the user to note down (low-tech save system!).

*Genres:* text adventure, puzzle.

---

## 8. Demo / effects

### 8.1 `IM2-HANDLER! ( xt -- )` — deep  *(shipped)*

Shipped. `IM2-HANDLER! ( xt -- )` installs a colon word as the IM 2
frame-interrupt handler; companions are `IM2-HANDLER@ ( -- xt )` and
`IM2-OFF ( -- )`. The runtime shim auto-saves AF/HL/BC/DE/IX/IY on
entry and finishes with `EI; RETI`, so the handler body is plain
Forth (must be stack-neutral on both stacks). The 257-byte vector
table at `$B800–$B900` and the 3-byte JP slot at `$B9B9` are
auto-emitted under liveness — programs that don't use IM 2 stay
byte-for-byte identical to before.

Working examples: `examples/im2-rainbow/` (border cycler), and the
AY music drivers `examples/im2-music/` and `examples/im2-bach/` —
all three run a foreground thread and an ISR concurrently.

See [`docs/im2-architecture.md`](im2-architecture.md) for the full
design, including simulator-side mechanics (frame-rate auto-fire,
EI-pending one-instruction delay, the 257-byte floating-bus trick)
and the milestone-by-milestone test counts.

*Genres:* demo, arcade (audio), puzzle.

### 8.2 `BORDER-RACE ( -- )` — spec

Well-known trick: change the border colour at precise T-states within the
frame to produce rainbow stripes. Not really a primitive but a pattern that
wants documented examples and a timing helper.

```forth
variable stripe-row
: rainbow-tick
    stripe-row @ 8 mod border
    1 stripe-row +!
    wait-frame ;
```

Timing is tight on 48K; requires disabling interrupts during the critical
window.

*Genres:* demo only.

### 8.3 `HALT ( -- )` — primitive  *(shipped)*

`halt` is a program terminator — emits Z80 `HALT` and falls through
without dispatching. It's the clean stop signal for `zt test` and the
default end-of-program behaviour. For *frame-sync without consuming
CPU*, use `wait-frame` (§1) instead.

### 8.4 `LUT-SIN ( angle -- value )` — spec

256-entry sine lookup. Critical for plasma effects, movement, rotation.

```forth
create sine-table  256 allot   \ pre-computed at build time
: sin  ( angle -- -128..127 )  sine-table + c@ ;
```

Build-time generation: a directive `BUILD-SIN-TABLE` that fills the table at
compile time. Zero runtime cost.

A 64-entry sine implementation already ships at the example level —
see `examples/voxel-letter/lib/sin64.fs` and the sibling
`tests/gen_sine.py` host-side table generator. Promoting the pattern
to a stdlib helper plus a build-time directive is the open work.

*Genres:* demo.

---

## 9. Memory and lifecycle

Utility primitives that make game code easier without being genre-specific.

### 9.1 `2@ ( addr -- n1 n2 )`, `2! ( n1 n2 addr -- )` — spec

Two-cell fetch/store. Useful for (x, y) coordinate pairs: one memory access
instead of two.

### 9.2 `CELL+ ( addr -- addr' )`, `CELLS ( n -- n*2 )` — spec

ANS Forth words for portable cell arithmetic. Shallow but make library code
genre-independent.

### 9.3 `CMOVE> ( src dst len -- )` — spec

Reverse-direction `CMOVE` for overlapping copies. Needed by scroll
primitives.

### 9.4 `FREE ( -- addr )` — spec

Return the current dictionary pointer; useful as a "high water mark" for
custom allocators.

---

## 10. Priorities by genre

If you're building one game today, here's the minimum viable primitive
set per genre. Items already shipped (✅ `KEY`, `KEY?`, `KEY-STATE`,
`WAIT-FRAME`, `BEEP`, `AT-XY`, plus stdlib `rnd`/`random`/`seed!`,
`attr!`, `grid@`/`grid!`, the AY surface, and `IM2-HANDLER!`) are
listed for completeness but don't need new work.

| Genre | Must-have additions beyond current `PRIMITIVES` + stdlib |
|-------|----------------------------------------------------------|
| **Text adventure** | `ACCEPT`, `COMPARE`, `>UPPER`. Optional: `WORD`, `SAVE-SLOT`. |
| **Puzzle / board** | Native fast `RND` (Xorshift). `attr!`/`grid@`/`grid!` already shipped. |
| **Action / arcade** | `KEMPSTON`, `XOR-SPRITE`. Native fast `RND` if profile pins LCG. |
| **Demo / effects** | `PLOT`, `LINE`, `LUT-SIN`. `IM2-HANDLER!`, `SCROLL-ATTR` already shipped. |

The shared spine — frame-paced input — is done. Each genre's residual
list above is one to three primitives, not a year of work.

---

## 11. Graceful-degradation discipline

Per the hardware-target choice: 48K and 128K both supported today;
design primitives so code written for 128K runs on 48K with predictable
behaviour rather than refusing to compile.

Practical rules:

- **AY primitives are no-ops on 48K.** A game using `ay-tone-a!` produces
  silent output on 48K but still runs. No conditional compilation
  required in user code.
- **`128k?` returns `0` on 48K.** User code can `128k? if ... then` to
  gate 128K-only features. The banking primitives (`bank@`, `bank!`,
  `raw-bank!`) themselves are unsafe on 48K — gate calls behind the
  `128k?` check.
- **`SOUND ( freq dur -- )` dispatches.** On 48K it compiles to `BEEP`
  with a coarse frequency conversion; on 128K it writes AY registers.
  User code reads the same.
- **`KEMPSTON` returns 0 when no joystick is present.** No crash, no
  detection ceremony.

The pattern to avoid: primitives that `ABORT` or require a runtime
`AVAILABLE?` check. The runtime should make absent hardware look like
"everything's fine but nothing happens."
