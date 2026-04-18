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
- **Deep** primitives include a Z80 register-plan sketch and, where novel, an
  opcode outline in the style of `PLAN.md`.
- Cell-width is 16-bit throughout (zt's only cell size).

---

## 1. Timing and frame synchronization

The single most missing capability. Every genre needs it: text adventures for
cursor blink, puzzles for animations between moves, arcade for consistent
speed, demo for effects.

### `WAIT-FRAME ( -- )` — deep

Block until the next 50 Hz frame interrupt. After it returns, the program has
~19,968 T-states (about 4,000 dispatches) before the next interrupt.

```
WAIT-FRAME:
        halt
        jp   NEXT
```

The runtime must install an IM 1 or IM 2 handler that increments
`_frame_counter`. Simplest route: IM 1, handler at `$0038` in user code
(overriding ROM's handler while our program runs), `EI` at program start.

Should be perhaps changed for IM2 (e.g. AY music)

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

Pure Forth; no new primitive needed once `WAIT-FRAME` exists.

*Genres:* all.

---

## 2. Random numbers

Every genre wants randomness: dungeon layout (adventure), shuffling (puzzle),
enemy AI (arcade), dithering/noise (demo).

### `RND ( -- n )` — deep

16-bit linear-congruential generator. Returns a pseudo-random cell.

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

(This is a standard Z80 Xorshift-like PRNG — ~40 T-states per call. Much
faster than a full LCG.)

*Genres:* all.

### `SEED ( n -- )` — spec

Write to `_rnd_seed`. Needed for reproducible puzzle layouts and replay
debugging.

### `RANDOM ( n -- 0..n-1 )` — spec

```forth
: random  ( n -- 0..n-1 )  rnd swap u/mod drop ;
```

Not quite uniform for non-power-of-two `n`, but good enough for games.

*Genres:* puzzle, arcade, demo.

---

## 3. Input

### 3.1 Fix `KEY` and `KEY?` (currently broken on real hardware)

Blocking item — see `COMPILER-ROADMAP.md` §1.1. Until this is fixed, no
interactive program runs outside the simulator. Doesn't add a new primitive,
just makes the existing one work.

### 3.2 `KEY-STATE ( keycode -- flag )` — deep

Non-blocking check of whether a specific key is currently held down. This is
what an arcade game wants: every frame, "is `LEFT` pressed? is `FIRE`
pressed?" without blocking.

```forth
: tick
  wait-frame
  'a' key-state if player-left then
  's' key-state if player-right then
  'm' key-state if fire then ;
```

Implementation reads the right half-row port and tests the specific bit.
Keycode-to-(port, bit) mapping lives in a 96-byte table built at compile time.

```
KEY-STATE: ( keycode -- flag )
        ld   a, l                 ; keycode low byte
        cp   'A'
        jr   c, .done             ; too low
        cp   'Z'+1
        jr   nc, .done            ; too high
        sub  'A'
        ld   e, a
        ld   d, 0
        ld   hl, _keytable
        add  hl, de
        add  hl, de               ; 2 bytes per entry: (port_high, bitmask)
        ld   b, (hl)              ; port high byte
        ld   c, $FE
        in   a, (c)
        inc  hl
        and  (hl)
        ld   hl, 0
        jr   nz, .done            ; bit high = not pressed
        dec  hl                   ; -1 = pressed
.done:  jp   NEXT
```

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

### 4.5 `INK ( n -- )`, `PAPER ( n -- )`, `BRIGHT`, `FLASH` — spec

Set the "current" attribute; subsequent `EMIT` uses it. Each is a shallow
primitive that reads/writes a byte at `_current_attr`. `CLS` already mixes
ink and paper — these generalize.

### 4.6 `ATTR! ( attr col row -- )` — spec

Already effectively implemented in the plasma example as user-level code
(`attr!` in `examples/plasma/lib/screen.fs`). Promote it to the primitive
set so it's available without a library.

### 4.7 `AT-XY ( col row -- )` — spec

Move the `EMIT` cursor. Already have `reset-cursor`; this generalizes to any
position.

*Genres:* all.

---

## 5. Graphics — sprites

### 5.1 `XOR-SPRITE ( addr col row -- )` — deep

Blit an 8-wide × H-tall byte-aligned sprite via XOR. Two draws = erase.

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

### 5.2 `PRE-SHIFT ( src dst -- )` — deep

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

Full-screen 8-pixel scroll. Roughly 200 lines of `LDIR` or unrolled
sequences. Expensive but sometimes essential (scrolling platformer, demo
effects).

```forth
: scroll-frame  wait-frame scroll-left ;
```

Graceful degradation: on 48K, full-screen scroll is too slow for 50fps. Ship
`PARTIAL-SCROLL ( top-row rows -- )` that scrolls only a band of the screen.

*Genres:* arcade, demo.

### 5.4 `TILE@ ( x y -- tile )`, `TILE! ( tile x y -- )` — medium

Tile-map read/write. Assumes the app has registered a tile map base address
with dimensions. Useful for platformer-style collision detection and
puzzle-grid logic.

Simpler formulation as a Forth word over `C@` and `C!`:

```forth
variable tile-map
variable map-width
: tile-addr   ( x y -- addr )  map-width @ * + tile-map @ + ;
: tile@       tile-addr c@ ;
: tile!       tile-addr c! ;
```

Keep it in the stdlib rather than making it a primitive, unless profiling
shows it's hot.

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

### 6.1 `BEEP ( duration pitch -- )` — deep (48K)

Classic Spectrum beeper loop: toggle bit 4 of port `$FE` at a cycle-counted
interval. Duration in frames, pitch in Z80 half-periods.

```
BEEP:   ; ( duration pitch -- )
        pop  de                 ; DE = duration (frames)
        push de                 ; keep
        di
.frame: ld   b, 50              ; approx cycles per frame at this pitch
.tone:  ld   a, $10             ; beeper bit
        out  ($FE), a
        ld   c, H               ; pitch-derived half-period wait
.wait1: dec  c : jr nz, .wait1
        xor  a
        out  ($FE), a
        ld   c, H
.wait2: dec  c : jr nz, .wait2
        djnz .tone
        dec  de
        ld   a, d : or e
        jr   nz, .frame
        ei
        pop  de
        pop  hl
        jp   NEXT
```

Not polyphonic; game logic freezes during the tone. Adequate for sound
effects (short blips).

*Genres:* arcade, puzzle (feedback clicks), demo.

### 6.2 `CLICK ( -- )` — spec

Single border toggle, ~2 ms. The shortest audio feedback. Used for "button
pressed," "key accepted," "score tick."

```forth
: click  16 border 7 border ;
```

(Cheap; beeper is wired to the border port.)

*Genres:* all.

### 6.3 `AY!`, `AY@` — deep (128K only)

Write / read AY registers. Trivial wrappers over ports `$FFFD` (register
select) and `$BFFD` (data write). Meaningless on 48K.

```
AY!:    ; ( value register -- )
        pop  de                 ; DE = value
        ld   bc, $FFFD
        out  (c), l             ; select reg
        ld   bc, $BFFD
        out  (c), e             ; write value
        pop  hl
        jp   NEXT
```

48K graceful degradation: at compile time, detect a `--48k` target and
compile these to no-ops plus a warning at build time. Or ship them as
conditionals that silently do nothing — preferable so adventure games can
attempt sound without branching logic everywhere.

*Genres:* arcade, demo, puzzle.

### 6.4 Tracker-style driver — architectural, not primitive

A 128K AY driver runs from the interrupt handler, reads a tune format each
frame, updates AY registers. Out of scope for "primitives" but worth
mentioning because its existence determines what data format the primitives
should expose. See `02-improvements.md` §4.2.

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

### 8.1 `IM2-HANDLER! ( addr -- )` — deep

Install `addr` as the IM 2 interrupt handler. Enables raster-synced effects,
per-line palette changes, music playback.

Requires a 257-byte aligned vector table; handler runs every 50th of a
second (or more frequently with careful port `$FE` timing).

*Genres:* demo.

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

### 8.3 `HALT ( -- )` — already exists as primitive

The existing `halt` primitive is already right for demos that want to sync
to the next interrupt without consuming CPU. Document it as such.

### 8.4 `LUT-SIN ( angle -- value )` — spec

256-entry sine lookup. Critical for plasma effects, movement, rotation.

```forth
create sine-table  256 allot   \ pre-computed at build time
: sin  ( angle -- -128..127 )  sine-table + c@ ;
```

Build-time generation: a directive `BUILD-SIN-TABLE` that fills the table at
compile time. Zero runtime cost.

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

If you're building one game today, here's the minimum viable primitive set
per genre:

| Genre | Must-have additions beyond current `PRIMITIVES` |
|-------|-------------------------------------------------|
| **Text adventure** | Fix `KEY` on real hardware, `ACCEPT`, `COMPARE`, `>UPPER`. Optional: `WORD`, `SAVE-SLOT`. |
| **Puzzle / board** | Fix `KEY`, `WAIT-FRAME`, `RND`, `RANDOM`. Optional: `ATTR!` as primitive, `TILE@`/`TILE!`. |
| **Action / arcade** | Fix `KEY`, `WAIT-FRAME`, `KEY-STATE`, `KEMPSTON`, `XOR-SPRITE`, `BEEP`, `RND`. |
| **Demo / effects** | `WAIT-FRAME`, `IM2-HANDLER!`, `PLOT`, `LINE`, `LUT-SIN`, `BEEP`. |

The shared spine — fix `KEY`, add `WAIT-FRAME`, `RND` — costs maybe two days
of work and unblocks every genre. Everything else layers on top.

---

## 11. Graceful-degradation discipline

Per the hardware-target choice: 48K now, 128K later, design primitives so
code written for 128K runs on 48K with predictable behavior rather than
refusing to compile.

Practical rules:

- **AY primitives are no-ops on 48K.** A game using `AY!` produces silent
  output on 48K but still runs. No conditional compilation required in user
  code.
- **Bank-switch primitives return false on 48K.** `BANK ( n -- ok )` returns
  0 (false) on 48K; user code can `IF BANK THEN` to gate 128K-only features.
- **`SOUND ( freq dur -- )` dispatches.** On 48K it compiles to `BEEP` with
  a coarse frequency conversion; on 128K it writes AY registers. User code
  reads the same.
- **`KEMPSTON` returns 0 when no joystick is present.** No crash, no
  detection ceremony.

The pattern to avoid: primitives that `ABORT` or require a runtime
`AVAILABLE?` check. The runtime should make absent hardware look like
"everything's fine but nothing happens."
