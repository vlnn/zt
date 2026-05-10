[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

[![tests](https://github.com/vlnn/zt/actions/workflows/test.yml/badge.svg)](https://github.com/vlnn/zt/actions/workflows/test.yml)

A Python-hosted toolchain that takes a `.fs` Forth source file and emits a Spectrum
`.sna` snapshot you can drop into Fuse, ZEsarUX, or a real 48K via divMMC. The
generated image uses indirect-threaded code, so most of a program is a flat list of
16-bit word addresses with hand-written Z80 primitives at the leaves.

> **New here?** [`docs/getting-started.md`](docs/getting-started.md) is the 60-second tour — install, build an example, write hello world, and pointers into the rest of the docs.

---

## Part 1 — Getting started (external onboarding)

### Why zt

The 48K Spectrum has ~42 KB of usable RAM, an 8-bit Z80, and a 256×192 bitmap
screen with character-cell colour attributes. You could write a game in Z80
assembly and re-implement control flow every time. Or you could write C with
z88dk and fight the codegen. zt sits in between: a tight language that
compiles to code you can read byte-for-byte, a simulator that runs your code
in pytest, and a debugger that maps addresses back to source lines.

The tradeoff: threaded code is denser than hand-rolled assembly and slower than
it. How much slower depends on the workload. A tight loop of cheap primitives
(the inner pixel of a scroll routine) is 10–15× slower because each primitive
dispatch costs ~79 T-states regardless of how trivial the work is. Code
dominated by heavy primitives — multiply, divide, blits, AY writes — runs within
1.5–3× of equivalent assembly because the dispatch is amortized. Typical mixed
game code lands somewhere between, and the inliner pulls it tighter where it
can.

### Installing

```
uv sync
make test
make examples        # build build/*.sna from every example
```

### Demo

The plasma at startup — `plasma-init` paints the full attribute area once,
then the foreground loop reads QAOP / 6789 keys and pans the buffer through
`scroll-attr` every frame:
<video src="https://github.com/user-attachments/assets/8d94c131-63b9-4cdb-947b-1136e4accac9" controls muted loop preload="metadata" width="350" height="280"></video>

Source layout, the precomputed phase-buffer trick, and a code walkthrough:
[`examples/plasma4/README.md`](examples/plasma4/README.md).

A simple reaction game — a random digit appears, and after the user's
keypress (hopefully matching) a small statistics line follows:
<video src="https://github.com/user-attachments/assets/88a09ff6-5578-44d9-842c-bbb89352ec7d" controls muted loop preload="metadata" width="350" height="280"></video>

### Hello world

```forth
\ hello.fs
: greet   ." HELLO SPECTRUM" cr ;
: main    7 0 cls greet begin again ;
```

```
zt build hello.fs -o hello.sna --map hello.map
```

Load `hello.sna` in Fuse: white background, black text, idle loop. The
`.map` is a Fuse-compatible symbol map so your debugger shows `greet` and
`main` instead of raw addresses.

### The development loop

Two main feedback loops.

**Unit tests in pytest.** The simulator is importable as `zt.sim` and runs
the same compiled bytes the `.sna` contains, exposing screen memory, border
writes, and stdin as Python attributes:

```python
from pathlib import Path
from zt.compile.compiler import Compiler
from zt.sim import Z80

def test_plasma_writes_attrs():
    c = Compiler(include_dirs=[Path("examples/plasma4")])
    c.compile_source(Path("examples/plasma4/main.fs").read_text())
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.pc = c.words["_start"].address
    m.run(max_ticks=500_000)
    assert m.mem[0x5800] != 0x00, "attr byte (0,0) should be painted"
```

When something misbehaves, `zt inspect --symbols out.fsym` decompiles the
image back to a threaded-code listing with Forth word names, so "why is
`draw` 18 bytes longer than I expected" becomes answerable.

**Profiling.** The simulator counts real Z80 T-states per instruction, and
the `zt profile` subcommand turns that into a word-level report:

```
$ zt profile --source hello.fs --max-ticks 100000 --words emit,cr,type

Word                  Calls     Self   Self%       Incl   Incl%      Avg
------------------------------------------------------------------------
type                     49    68546    6.4     920986   86.1    18795
emit                    978   524477   49.0     919005   85.9      939
cr                       48      816    0.1     909782   85.1    18953

Total: 1069450 T-states across 100000 instructions
```

`Self` is T-states executed directly in the word's body. `Incl` adds the
T-states spent in everything that word called. Above, `cr`'s self time is
trivial (0.1 %) but its inclusive time dominates because it drives `emit`,
and `emit` is where the cycles go — 49 % of the program inside it.

Typical optimization workflow:

```
zt profile --source prog.fs --save baseline        # snapshot before
# edit prog.fs, change a primitive, try an inlining
zt profile --source prog.fs --baseline baseline.zprof --words HOT-WORD
```

The diff mode prints base/current/Δ/Δ% columns sorted by absolute delta,
so you see at a glance whether a change helped, regressed, or moved
nothing. For CI, `--fail-if-slower 5` returns exit 1 if any selected word
regressed by more than 5 %.

Both `--source file.fs` (compile-then-run) and `--image file.sna` (with a
sibling `.map`) are accepted; `--json` emits the same data for scripting.
See `zt profile --help` for the full flag list.

### Showcase: a brick-breaker

https://github.com/user-attachments/assets/ccd2a1de-936c-486b-bd21-b7f134375118

`examples/arkanoid/` is a small Arkanoid-like — paddle, ball, breakable
bricks, lives, score — and exercises most of what's needed for a real ZX
game on top of `plasma`'s attribute work: 8×8 sprite blits, pixel-resolution
ball motion, per-frame physics, keyboard input, and a HUD. Around 5 KB
compiled, split across six modules under `lib/`:

```
examples/arkanoid/
├── main.fs              ← entry — calls arkanoid then halt
└── lib/
    ├── sprites.fs       ball-shifted, blank-shifted, paddle-{left,mid,right}, brick-tile, wall-tile
    ├── bricks.fs        30×4 brick grid via stdlib grid.fs, ball-center collision
    ├── paddle.fs        char-aligned paddle, throttled O/P motion, paddle-vel tracking
    ├── ball.fs          physics: walls, ceiling, paddle (zone-based), brick bounces, floor-loss
    ├── score.fs         score, lives, hud-dirty flag
    └── game.fs          init-level, game-step, game-loop, top-level arkanoid
```

The angle of the bounce off the paddle is the gameplay trick worth calling
out:

```forth
\ Six 4-pixel zones across a 24-pixel paddle: edges deflect steepest,
\ centre gentlest. No zero zone — paddle hits always retain horizontal motion.
\   offset    0..3   4..7   8..11  12..15  16..19  20..23
\   new dx    -3     -2     -1     +1      +2      +3
: zone-dx            ( hit-off -- dx )
    dup  4 < if drop -3 exit then
    dup  8 < if drop -2 exit then
    dup 12 < if drop -1 exit then
    dup 16 < if drop  1 exit then
    dup 20 < if drop  2 exit then
    drop  3 ;

: paddle-bounce-dx   ( -- dx )
    ball-x @ 4 + paddle-left-px - zone-dx
    paddle-vel @ + clamp-dx ;
```

A few details worth pointing out:

- **Pre-shifted ball, char-aligned bricks.** The ball uses `BLIT8X` /
  `BLIT8XC` (pre-shifted, pixel-aligned) so it can move at pixel resolution;
  bricks and paddle use `BLIT8` / `BLIT8C` (char-aligned). Mixing the two
  avoids paying the pre-shift cost on the static pieces.
- **Cell-level background restore.** Erasing the ball naively would scrub
  brick pixels off the screen. Before painting the ball each frame,
  `restore-old-cells` repaints every cell the previous footprint covered to
  its actual background — a live brick if one's there, blank otherwise.
- **Variable bounce angles plus paddle "english".** `paddle-bounce-dx` adds
  the paddle's per-frame column delta (`paddle-vel`) to the zone-derived dx,
  then clamps to ±3, so a paddle moving into the contact pulls the bounce
  further in that direction.
- **HUD dirty-bit.** `mark-hud-dirty` is set only when score or lives
  change; the per-frame body skips the ROM `EMIT` path most of the time.
  Cuts ~2.4k T-states per frame in the common case.
- **Frame ordering.** Render at the start of the frame (top border, beam
  not yet on the visible area), physics at the end. The visible image is
  finalised before the beam reaches it.

Build it:

```
make build/arkanoid.sna
```

Controls: `O` left, `P` right. Knock out all 120 bricks to wrap to a fresh
level; you have 3 lives. End-to-end tests covering paddle bounds, brick
count, score, paddle-pixel integrity, ball-dx variation, and no-pixel-trail
invariants live in `examples/arkanoid/tests/test_arkanoid.py`.

### Showcase: a language model on a stock 48K

`examples/zlm-tinychat-48k/` runs a small conversational language model
(256→256→192→128→40 MLP, 2-bit packed weights, ~35 KB of parameters total)
on an unmodified 48K Spectrum. Type a query, press ENTER, get a
character-by-character reply:


https://github.com/user-attachments/assets/65cb033d-32ba-4934-9465-9a8b3b5f6261


The model is HarryR's [Z80-μLM](https://github.com/HarryR/z80ai) — a
delightful piece of work that quantizes a tiny chatbot down to where it'll
comfortably run inside a Z80's 64 KB address space. The trigram hash
encoder (input → 128 buckets, typo-tolerant and word-order invariant) is
what gives the model its surprising "vibe" matching at that parameter
budget. Huge thanks and full credit to HarryR for the model itself, the
training pipeline, and the original ZX Spectrum target work — without that
foundation this example wouldn't exist.

The zt-side contribution is the Forth port and a memory-map arrangement
that makes it fit on a stock 48K rather than the 128K a more naive layout
would need. Activations get hoisted to fixed RAM addresses outside the
compiled image, biases shrink from 16-bit to 8-bit signed, and the
third-layer activation buffer parks in the 48K printer-buffer region
(plain RAM the display hardware never reads), which closes the budget
without scribbling on the screen during inference. See
`examples/zlm-tinychat-48k/README.md` for the byte-level layout.

Build it the same way you'd build any other example:

```
make build/zlm-tinychat-48k.sna
```

Load the resulting `.sna` in Fuse, ZEsarUX, or a real 48K via divMMC.

---

### Showcase: concurrent foreground + ISR via IM 2

zt supports the Z80's interrupt mode 2 — the dispatch path real Spectrum
games and music drivers use to run code at every ULA frame boundary while
the foreground thread keeps going. Three Forth primitives cover the
user-facing surface:

- `IM2-HANDLER! ( xt -- )` installs a colon word as the IM 2 handler.
  Internally it writes the xt into a thread cell, sets `I` to the
  vector-table page, and switches the CPU to IM 2.
- `IM2-HANDLER@ ( -- xt )` reads back the currently installed xt.
- `IM2-OFF ( -- )` reverts to IM 1 with interrupts disabled.

The 257-byte vector table at `$B800–$B900` and the 3-byte JP slot at
`$B9B9` are auto-emitted whenever any IM 2 primitive is reachable from
`_start` (compile-time liveness). Programs that don't use IM 2 stay
byte-for-byte identical to before.

Because the handler is a colon word, the body is plain Forth. A runtime
shim auto-saves AF/HL/BC/DE/IX/IY on entry and finishes with `EI; RETI`,
so user code doesn't write the prologue/epilogue or touch NEXT machinery
— it just has to be stack-neutral on both stacks.

`examples/im2-rainbow/` is the worked demo. The handler cycles the border
through eight Spectrum colours once per frame; the foreground word loops
`random-letter emit` indefinitely. Both run together — you see the border
stripe at exactly 50 Hz while the screen continuously fills with random
letters.

```
examples/im2-rainbow/
├── main.fs              ← entry; clears screen, calls rainbow
├── app/
│   └── rainbow.fs       ← ISR (plain Forth), random-letter, install + spew loop
└── tests/
    ├── test_random_letter.fs    ← Forth unit test on the helper
    └── test_im2_rainbow.py      ← acceptance: build, run, assert frame
                                   interrupts, border cycle, JP slot populated
```

The ISR itself, in full:

```forth
variable border-tick

: rainbow-isr  ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: rainbow  ( -- )
    ['] rainbow-isr im2-handler!
    ei
    begin random-position at-xy random-letter emit again ;
```

Build:

```
zt build examples/im2-rainbow/main.fs -o build/im2-rainbow.sna
```

For users who want raw control over the ISR cycle budget, the
single-file `examples/im2-rainbow.fs` writes the same handler in `:::`
assembly — push everything you touch, end with `EI; RETI`, avoid NEXT.
Compiles to a tighter ISR; useful when timing is critical.

For the design — simulator-side mechanics (frame-rate auto-fire,
EI-pending one-instruction delay, the 257-byte floating-bus trick) and
the milestone-by-milestone test counts — see
[`docs/im2-architecture.md`](docs/im2-architecture.md).

---

## Part 2 — How it works (internal reasoning)

### Execution model: indirect-threaded code

A compiled zt program is a flat list of 16-bit addresses. Each address
points to a primitive written in Z80, and each primitive ends with a
dispatch to the next address in the list. The register allocation is fixed:

| Register | Role |
|----------|------|
| `HL` | Top of data stack (TOS), kept in registers |
| `SP` | Data stack pointer (grows down from `$FF00`) |
| `IX` | Instruction pointer into the threaded code list |
| `IY` | Return stack pointer (grows down from `$FE00`) |

Keeping TOS in `HL` is the single biggest performance decision. Roughly
half of primitives never touch memory — `DUP` is `PUSH HL` + dispatch,
`SWAP` is `EX (SP),HL` + dispatch, `+` is `POP DE; ADD HL,DE` + dispatch.
At three to eight T-states per opcode, that matters.

Using `SP` as the data stack lets us use `PUSH`/`POP` directly for stack
manipulation — the densest, fastest Z80 stack instructions — at the cost
of keeping the Spectrum's ROM calls mostly off-limits (they use `SP`). We
own the stack discipline end-to-end, which is why `EMIT` writes directly
to screen memory rather than calling `RST $10`.

### `NEXT`: the dispatch sequence

`NEXT` is the 12-byte, six-instruction sequence that advances IX and
jumps to the next word:

```
LD   E,(IX+0)      ; 19 T   3 bytes
LD   D,(IX+1)      ; 19 T   3 bytes
INC  IX            ; 10 T   2 bytes
INC  IX            ; 10 T   2 bytes
PUSH DE            ; 11 T   1 byte
RET                ; 10 T   1 byte
```

`PUSH DE; RET` is a 2-byte indirect jump to the address in DE that
preserves HL. The natural alternative — `LD H,D; LD L,E; JP (HL)` — is
one byte shorter but trashes HL, which holds TOS. Briefly between PUSH
and RET, the dispatch's return address sits at the top of the data stack
space; an interrupt during that window would push its return PC onto
user data, so dispatch paths run with interrupts disabled.

By default the compiler inlines `NEXT` at every dispatch site rather
than jumping to a shared copy (`inline_next=True` in `Compiler.__init__`).
This trades 9 bytes per primitive (12-byte inline NEXT vs. 3-byte `JP NEXT`)
against saving the `JP NEXT` round-trip — a worthwhile swap for
code-size-dominant programs that still have hot inner loops.

### Pipeline

```
source (.fs)
   │  tokenizer.py          → Token(value, kind, line, col, source)
   ▼
tokens
   │  compiler.py           → IR cells (PrimRef, ColonRef, Literal, Branch, Label)
   ▼
IR (list[Cell] per colon word)
   │  peephole.py           → fuse patterns like (1, '+') → '1+'
   │  inline_bodies.py      → splice primitive bodies inline when profitable
   │  liveness.py           → reachability set for tree-shaking (default-on)
   ▼
IR (optimized, live cells only)
   │  ir.resolve()          → bytes (little-endian word addresses)
   │  code_emitter.py       → glue to Asm
   ▼
Asm (opcode bytes + labels + fixups)
   │  asm.resolve()         → resolve labels, patch jr/jp displacements
   ▼
machine code
   │  sna.build_sna()       → header + 48K RAM image
   ▼
output.sna
```

The IR is deliberately tiny: six dataclasses (`PrimRef`, `ColonRef`,
`Literal`, `Label`, `Branch`, `StringRef`) plus a `resolve()` function
that walks them and produces bytes. `Label` cells are zero-width and
define addresses; `Branch` cells are 4 bytes (opcode ref + target
address); all others are 2 bytes. This uniformity is what makes the
peephole optimizer easy to write: patterns match on primitive names, not
on byte sequences.

### Three kinds of optimization

**Peephole.** Matches short sequences of IR elements and replaces them
with shorter ones. Nine entries today (`peephole.py:DEFAULT_RULES`)
covering the obvious wins: `0` becomes a reference to the `ZERO`
primitive (2 bytes) instead of `LIT` + a zero cell (4 bytes); `SWAP DROP`
becomes `NIP`; `OVER OVER` becomes `2DUP`. Rules are specificity-sorted
so longer matches win.

**Primitive inlining.** When a colon word's body consists only of
inlinable primitives, its compiled body gets replaced by the
concatenated primitive bodies with a single trailing dispatch.
Transformative for small helpers: `: mod32 31 and ;` goes from four
dispatches (LIT, 31, AND, EXIT) to three Z80 instructions plus one
dispatch. The inliner (`inline_bodies.py`) learns each primitive's body
by assembling its `create_*` function, recognising the trailing `JP NEXT`,
and stripping it. It only inlines primitives on an explicit whitelist
because some — `EMIT`, `DO`, anything with an absolute jump — aren't
relocation-safe.

A complementary tool is the `::` (force-inline) defining word. `::name
... ;` declares a colon word whose body is *always* spliced into its
callers. Useful for hot paths where the caller knows the inline cost is
worth it. Bodies may contain control flow (`if/else/then`,
`begin/until/while/repeat`, `do/loop/+loop`); they may not call other
colon words, use string literals, or contain `LEAVE`.

**Tree-shaking.** A liveness pass (`liveness.py`) walks the IR from
`main`/`halt`/`next`/`docol` and marks every reachable primitive, colon,
string, constant, variable, and `create` definition. The emitter then
builds a fresh image containing only the live set. On by default — `zt
build` auto-tree-shakes any program that uses supported features and
falls back to the eager build with a stderr warning when it can't.
`--tree-shake` is strict mode (fail rather than fall back); `--no-tree-shake`
opts out entirely. Typical savings: 4–77 % per program; the bundled suite
of 16 examples shrinks from ~134 KB to ~82 KB combined (40 % reduction).

### Debug surface

The real payoff of a clean IR is that every cell has a known source
location (`Token`), which propagates through to four output formats:

- `--map out.map` — Fuse or ZEsarUX symbol map
- `--sld out.sld` — sjasmplus Source Level Debug for ZEsarUX line stepping
- `--fsym out.fsym` — JSON host dictionary for `zt inspect`
- `zt inspect --symbols out.fsym` — decompiler that walks the threaded
  code list and prints it with Forth word names

When something crashes at `$A247`, you can `grep A247 out.map` and find
out it's line 23 of `plasma.fs`.

### Simulator

`src/zt/sim.py` is a purpose-built Z80 emulator — not a general one. It
implements only the opcodes the primitives use (~120 distinct
instructions) and trades away most undocumented flag side-effects and
undocumented opcodes. In exchange it's a thousand-odd lines, runs fast
enough that a full test suite passes in under half a minute, and exposes
cleanly hookable inputs (`input_buffer`) and outputs (`_outputs`, screen
memory).

Two counters run alongside each step. `_ticks` is a Python-side
instruction count used as the `max_ticks` safety budget for bounded
runs. `_t_states` is the real Z80 cycle count, accumulated from a
per-opcode cost table that handles the variable cases — (HL)-indirect
operands, taken vs. not-taken branches, LDIR's per-iteration loop. The
`Profiler` samples both axes per instruction, which is what lets `zt
profile` show inclusive T-state timing per word.

Dispatch is table-driven: 256 opcode slots populated at `Z80.__init__`,
each a bound method plus a base T-state cost. This replaced the original
elif ladder and is both faster (one list index vs. walking a chain of
comparisons) and easier to extend — adding a new opcode is one
`reg(op, handler, cost)` line in `_build_ops_table`.

Keyboard input goes through the real Spectrum matrix: `KEY`, `KEY?`, and
`KEY-STATE` are Z80 primitives that issue `IN A,($FE)` across the eight
half-rows and decode the result. The simulator intercepts reads from
port `$FE` and synthesises matrix responses from its `input_buffer`, so
tests can feed key presses as Python strings and the exact same compiled
bytes run unchanged on real hardware.

### Limitations worth knowing about

- **No AY tracker.** Register-poke primitives ship in `stdlib/ay.fs`
  (`ay-set`, `ay-mixer!`, `ay-tone-{a,b,c}!`, `ay-vol-{a,b,c}!`,
  `ay-noise!`) and `examples/im2-bach/` is a working two-voice player
  driven from an IM 2 ISR, but a stdlib-factored tune-format driver is
  still open.
- **Sprites are basic but present.** Seven `BLIT8`/`MULTI-BLIT` family
  primitives (see `docs/primitives.md` and `examples/sprite-demo/`) cover
  char-aligned and pixel-aligned 8×8 blits. There's no built-in pre-shift
  table generator yet (the caller prepares the eight shifted copies), no
  XOR / transparency-mask variant, and no full-screen pixel scroll —
  attribute-level `SCROLL-ATTR` ships and is what the plasma demo uses.
- **Signed division is in stdlib, not in primitives.** `*` is a
  primitive but `/`, `/MOD`, `MOD` are defined in
  `src/zt/stdlib/core.fs` on top of a single unsigned `U/MOD` primitive.
  Fine for slow code, too slow for inner loops.
- **No `.tap` output.** Output formats are `sna`, `z80`, and `bin`.
  Loading on real hardware via `.tap` is on the roadmap.

128K banking *is* supported — see `--target 128k`, the bundled
`examples/plasma-128k/` example, and `docs/128k-architecture.md`.

Open items above and others are tracked in `docs/COMPILER-ROADMAP.md`
and `docs/FORTH-ROADMAP.md`.

## Credits

- **HarryR** — for [Z80-μLM](https://github.com/HarryR/z80ai), the tiny
  quantized language model that makes `examples/zlm-tinychat-48k/`
  possible. The model architecture, the trigram-hash input encoder, the
  quantization-aware training pipeline, and the original ZX Spectrum port
  are all his work; the zt-side contribution is just a Forth
  reimplementation and a memory-map rearrangement to fit a stock 48K.
  Sincere thanks for releasing such a fun and well-documented project,
  and warm regards.

[![Made in Ukraine](https://img.shields.io/badge/made_in-Ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
