# zt — Z80 Forth cross-compiler for the ZX Spectrum

A Python-hosted toolchain that takes a `.fs` Forth source file and emits a Spectrum
`.sna` snapshot you can drop into Fuse, ZEsarUX, or a real 48K via divMMC. The
generated image uses indirect-threaded code so most of a program is a flat list of
16-bit word addresses, with hand-written Z80 primitives at the leaves.

---

## Part 1 — Getting started (external onboarding)

### Why zt

The 48K Spectrum has 42KB of usable RAM, an 8-bit CPU, and a character-mapped
screen. You could write a game in Z80 assembly and spend weeks re-implementing
control flow every time. Or you could write C with z88dk and fight the
codegen. zt sits in between: you get a tight REPL-style language that compiles
to code you can read byte-for-byte, a simulator that runs your code in pytest,
and a debugger that maps addresses back to source lines.

The tradeoff: threaded code is roughly 3–5× slower than hand-rolled assembly,
but 3–5× denser than it as well. For most of what a Spectrum does — a puzzle
game, an adventure, a colourful demo, an editor — that's the right tradeoff.
For a tight inner loop (scroll, sprite blit) you drop to assembly or use zt's
inliner to fuse primitives into straight-line code.

### Installing

```
uv sync
make test
make examples        # build build/*.sna from every example
```

### Demo

The plasma example scrolling through the attribute area, and a short reaction
clip of the redraw loop under load:

<table>
  <tr>
    <td>
      <video src="https://github.com/user-attachments/assets/8d94c131-63b9-4cdb-947b-1136e4accac9" controls muted loop height="300">
        <a href="https://github.com/user-attachments/assets/8d94c131-63b9-4cdb-947b-1136e4accac9">plasma.mp4</a>
      </video>
    </td>
    <td>
      <video src="https://github.com/user-attachments/assets/210c49b6-2734-4e58-b51e-27babef91ff6" controls muted loop height="300">
        <a href="https://github.com/user-attachments/assets/210c49b6-2734-4e58-b51e-27babef91ff6">reaction.mp4</a>
      </video>
    </td>
  </tr>
  <tr>
    <td align="center"><sub><code>examples/plasma</code></sub></td>
    <td align="center"><sub>reaction loop</sub></td>
  </tr>
</table>

### Hello world

```forth
\ hello.fs
: greet   ." HELLO SPECTRUM" cr ;
: main    7 0 cls greet begin again ;
```

```
zt build hello.fs -o hello.sna --map hello.map
```

Load `hello.sna` in Fuse. White background, black text, infinite idle loop.
The `.map` is a Fuse-compatible symbol map so your debugger shows `greet` and
`main` instead of raw addresses.

### Happy path: the plasma example

`examples/plasma/` is the largest bundled example and exercises most of the
pipeline — multi-file includes, attribute-memory manipulation, nested counted
loops, and a tight redraw inner loop.

The source is split across three files that wire together with `REQUIRE`:

```
examples/plasma/
├── main.fs                    ← entry point; includes app/plasma.fs
├── lib/
│   ├── math.fs                ← : mod32 ( n -- n%32 ) 31 and ;
│   └── screen.fs              ← attrs, attr-addr, attr!
└── app/
    └── plasma.fs              ← wave table, plasma-cell, draw, animate
```

The core of it:

```forth
create wave
  0 c, 1 c, 2 c, 3 c, 4 c, 5 c, 6 c, 7 c,
  7 c, 6 c, 5 c, 4 c, 3 c, 2 c, 1 c, 0 c,
  \ ... 32 entries total, triangle wave

variable phase

: wave@        ( i -- n )      mod32 wave + c@ ;
: plasma-cell  ( col row -- attr )
    phase @ + wave@ swap
    phase @ + wave@
    xor
    3 lshift 64 or ;

: draw         ( -- )
    scr-rows 0 do
        scr-cols 0 do
            i j plasma-cell i j attr!
        loop
    loop ;

: step         ( -- )          1 phase +! ;
: animate      begin draw step again ;
```

Every identifier here is a Forth word — no syntax, no types, just a stream of
words that pushes and pops a parameter stack. `:` starts a definition, `;`
ends it. `( ... )` is a stack-effect comment and produces no code. `create
wave` followed by `c,` builds an inline byte array.

Build it:

```
zt build examples/plasma/main.fs -o plasma.sna --map plasma.map
```

You get a `.sna` that, when loaded, immediately starts mutating the attribute
area at `$5800–$5AFF`, producing the scrolling colour plasma.

### The development loop

Two main feedback loops.

**Unit tests in pytest.** The simulator is importable as `zt.sim` and runs
the same compiled bytes the `.sna` contains, exposing screen memory, border
writes, and stdin as Python attributes:

```python
def test_plasma_writes_attrs(tmp_path):
    out = build_sna(Path("examples/plasma/main.fs"))
    m = Z80()
    m.load(0x4000, out[27:])        # skip SNA header, load RAM
    m.run(max_ticks=500_000)
    assert m.mem[0x5800] != 0x00, "attr byte (0,0) should be painted"
```

When something misbehaves, `zt inspect --symbols out.fsym` decompiles the
image back to a threaded-code listing with Forth word names, so "why is
`draw` 18 bytes longer than I expected" becomes answerable.

**Profiling.** The simulator counts real Z80 T-states per instruction, and
the `zt profile` subcommand turns that into a word-level report:

```
$ zt profile --source examples/hello.fs --max-ticks 100000 --words emit,cr,type

Word                  Calls     Self   Self%       Incl   Incl%      Avg
------------------------------------------------------------------------
type                     49    68546    6.4     920986   86.1    18795
emit                    978   524477   49.0     919005   85.9      939
cr                       48      816    0.1     909782   85.1    18953

Total: 1069450 T-states across 100000 instructions
```

`Self` is T-states executed directly in the word's body. `Incl` adds the
T-states spent in everything that word called. In the example above, `CR`'s
self time is trivial (0.1 %), but its *inclusive* time dominates because it
drives `EMIT`, and `EMIT` is where the cycles actually go — 49 % of the
whole program spent directly inside it.

Typical workflow for optimization:

```
zt profile --source prog.fs --save baseline        # snapshot before
# edit prog.fs, change a primitive, try an inlining
zt profile --source prog.fs --baseline baseline.zprof --words HOT-WORD
```

The diff mode prints base/current/Δ/Δ% columns sorted by absolute delta, so
you see at a glance whether the change helped, regressed, or moved nothing.
For CI, `--fail-if-slower 5` returns exit 1 if any selected word regressed
by more than 5 %; wire it into a `make bench` step and you've got
regression-gated performance tests.

Both `--source file.fs` (compile-then-run) and `--image file.sna` (with a
sibling `.map`) are accepted; `--json` emits the same data for scripting.
See `zt profile --help` for the full flag list.

---

## Part 2 — How it works (internal reasoning)

### Execution model: indirect-threaded code

A compiled zt program is a flat list of 16-bit addresses. Each address points
to a primitive written in Z80, and each primitive ends with a dispatch to the
next address in the list. The register allocation is fixed:

| Register | Role |
|----------|------|
| `HL` | Top of data stack (TOS), kept in registers |
| `SP` | Data stack pointer (grows down from `$FF00`) |
| `IX` | Instruction pointer into the threaded code list |
| `IY` | Return stack pointer (grows down from `$FE00`) |

The choice to keep TOS in `HL` is the single biggest performance decision.
Roughly half of primitives never touch memory — `DUP` is `PUSH HL` + dispatch,
`SWAP` is `EX (SP),HL` + dispatch, `+` is `POP DE; ADD HL,DE` + dispatch. At
three to eight T-states per opcode that matters.

Using `SP` as the data stack lets us use `PUSH`/`POP` directly for stack
manipulation — the densest, fastest Z80 stack instructions — at the cost of
keeping the Spectrum's ROM calls mostly off-limits (they use `SP`). We own the
stack discipline end-to-end, which is why `EMIT` writes directly to screen
memory rather than calling `RST $10`.

`IX` as IP and `IY` as return stack is the inverse of the traditional fig-Forth
convention, and is motivated by Z80-specific opcode costs: `LD E,(IX+d)` is
19 T-states vs. `LD E,(IY+d)`'s 19 T-states (same), but the `(IX+d)` form is
slightly faster on the return stack in our access pattern because the IP fetch
happens on every dispatch. In practice either choice is defensible; the
codebase settled on this and the primitives are written around it.

### `NEXT`: the dispatch sequence

`NEXT` is the 6-byte sequence that advances IX and jumps to the next word:

```
LD   E,(IX+0)      ; 19 T
LD   D,(IX+1)      ; 19 T
INC  IX            ; 10 T
INC  IX            ; 10 T
PUSH DE            ; 11 T
RET                ; 10 T   ← jumps to (DE) via the SP trick
```

`PUSH DE; RET` is a four-byte indirect jump that's shorter and faster than
`LD A,(IX+0); ...; JP (HL)`. The tradeoff is that it briefly corrupts `SP`
with a value outside the data stack, which is fine because interrupts are
disabled during dispatch paths that care.

By default the compiler inlines `NEXT` at every dispatch site rather than
jumping to a shared copy (`inline_next=True` in `Compiler.__init__`). This
trades ~6 bytes per primitive against saving a `JP NEXT` / return trip — a
worthwhile swap for code-size-dominant programs that still have hot inner
loops.

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
   ▼
IR (optimized)
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
`Literal`, `Label`, `Branch`, `StringRef`) plus a `resolve()` function that
walks them and produces bytes. `Label` cells are zero-width and define
addresses; `Branch` cells are 4 bytes (opcode ref + target address); all
others are 2 bytes. This uniformity is what makes the peephole optimizer easy
to write: patterns match on primitive names, not on byte sequences.

### Two kinds of optimization

**Peephole.** Matches short sequences of IR elements and replaces them with
shorter ones. The rule set is nine entries today (`peephole.py:DEFAULT_RULES`)
and covers the obvious wins: `0` becomes a reference to the `ZERO` primitive
(2 bytes) instead of `LIT` + a zero cell (4 bytes); `SWAP DROP` becomes `NIP`
(saves one dispatch); `OVER OVER` becomes `2DUP`. Rules are specificity-sorted
so that longer matches win.

**Primitive inlining.** When a colon word's body consists only of
inlinable primitives, its compiled body gets replaced by the concatenated
primitive bodies with a single trailing dispatch. This is transformative for
small helpers: a one-line word like `: mod32 31 and ;` goes from four
dispatches (LIT, 31, AND, EXIT) to three Z80 instructions plus one dispatch.

The inliner (`inline_bodies.py`) learns what each primitive's body looks like
by assembling each `create_*` function, recognising the trailing `JP NEXT`,
and stripping it. It only inlines primitives on an explicit whitelist
(`INLINABLE_PRIMITIVES`) because some — `EMIT`, `DO`, anything with an
absolute jump — aren't relocation-safe.

### Debug surface

The real payoff of a clean IR is that every cell has a known source location
(`Token`), which propagates through to four output formats:

- `--map out.map` — Fuse or ZEsarUX symbol map
- `--sld out.sld` — sjasmplus Source Level Debug for ZEsarUX line stepping
- `--fsym out.fsym` — JSON host dictionary for `zt inspect`
- `zt inspect --symbols out.fsym` — decompiler that walks the threaded code
  list and prints it with Forth word names

When something crashes at `$A247`, you can `grep A247 out.map` and find out
it's line 23 of `plasma.fs`.

### Simulator

`src/zt/sim.py` is a purpose-built Z80 emulator — not a general one. It only
implements the opcodes the primitives use (~120 distinct instructions) and
trades away most undocumented flag side-effects and undocumented opcodes. In
exchange it's a thousand-odd lines, runs fast enough that a full test suite
passes in under half a minute, and exposes cleanly hookable inputs
(`input_buffer`) and outputs (`_outputs`, screen memory).

Two counters run alongside each step. `_ticks` is a Python-side instruction
count used as the `max_ticks` safety budget for bounded runs. `_t_states` is
the real Z80 cycle count, accumulated from a per-opcode cost table that
handles the variable cases — (HL)-indirect operands, taken vs. not-taken
branches, LDIR's per-iteration loop. The `Profiler` samples both axes per
instruction, which is what lets `zt profile` show inclusive T-state timing
per word.

Dispatch is table-driven: 256 opcode slots populated at `Z80.__init__`, each
a bound method plus a base T-state cost. This replaced the original elif
ladder and is both faster (one list index vs. walking a chain of comparisons)
and easier to extend — adding a new opcode is one `reg(op, handler, cost)`
line in `_build_ops_table`.

The simulator hooks `CALL $15E6` and `CALL $15E9` to synthesize `KEY` and
`KEY?` behaviour. This is a convenient shortcut for tests but a real-hardware
hazard: those two addresses are arbitrary ROM offsets and calling them on a
48K will do something between "nothing useful" and "lock up." See
`COMPILER-ROADMAP.md` §1.1 for the fix.

### Limitations worth knowing about

- **Keyboard on real hardware doesn't work yet.** `KEY` and `KEY?` are
  simulator stubs. You can run anything that prints or draws, but anything
  that reads input only works in the simulator.
- **No sound.** No beeper click, no AY.
- **No sprites.** `EMIT` renders characters through the ROM font, and `CMOVE`
  can blit bytes, but there's no pre-composed sprite primitive or
  pre-shifted mask support.
- **Signed multiply and divide live in `src/zt/stdlib/core.fs`** built on top of a
  single unsigned `U/MOD` primitive. Fine for slow code, too slow for inner
  loops.
- **No interrupt hook.** The compiled program runs with interrupts disabled
  in most dispatch paths. No frame-sync, no 50 Hz timer.
- **48K only.** No `.tap`, no 128K banking, no AY support.

Most of these are addressed in doc #2.
