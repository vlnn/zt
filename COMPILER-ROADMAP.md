# zt — Improvement roadmap

This document ranks proposed work by **impact** (how much does it unblock or
speed up real users?) and **difficulty** (how much code and risk?). Items inside
each tier are roughly sorted so that easier, higher-leverage work comes first.

Tiers:

1. **Fix soon** — high impact, low-to-medium difficulty. Blocking real-hardware
   use or leaving large wins on the table.
2. **Core quality** — high impact, medium difficulty. Compiler and runtime
   improvements that don't block anything today but compound over time.
3. **Reach** — medium impact, medium difficulty. Broadens what's possible
   without fundamentally changing the toolchain.
4. **Hardware frontier** — high impact, high difficulty. 128K, AY, interrupts.
5. **Developer experience** — medium impact, low-to-medium difficulty. Cheap
   quality-of-life improvements.
6. **Speculative** — uncertain impact, uncertain difficulty. Things worth
   considering but not planning.

---

## Tier 1 — Fix soon

### 1.1 Fix `KEY` and `KEY?` on real hardware

**Impact:** critical. Any interactive program — game, adventure, editor — is
currently simulator-only.
**Difficulty:** low. ~30 lines of Z80, no architectural change.

`src/zt/primitives.py` currently emits `CALL $15E6` / `CALL $15E9`. Those
addresses are the simulator's hook points, not real ROM entry points. On a 48K
they land mid-instruction in ROM and do nothing useful.

The fix is to replace both with a direct keyboard-port scan. The Spectrum
keyboard is wired to eight I/O ports, each reading five keys. A polling `KEY`
busy-loops reading the half-rows until any bit goes low, decodes the bit
position to an ASCII character (via a small ROM-resident or compiled table),
and returns.

```
; KEY — block until a key is pressed, return its keycode in HL
KEY:    push hl
.scan:  ld   bc, $FEFE        ; half-row 0 (CAPS SHIFT..V)
        ld   d, 8             ; 8 half-rows
.row:   in   a, (c)
        cpl
        and  $1F
        jr   nz, .found
        rlc  b                ; next half-row
        dec  d
        jr   nz, .row
        jr   .scan
.found: ; a = row-bits, b = row address high; decode to keycode via table
        ...
        ld   l, a
        ld   h, 0
        jp   NEXT
```

`KEY?` is the same scan without the busy loop — just returns a flag.

Change two constants and two `create_*` functions; add a small decode table.
The simulator hook can stay as a faster path, or the simulator can be taught
to synthesize port `$FE` reads from the `input_buffer`.

### 1.2 Word-level testing facade (`zt.testing`)

**Impact:** critical for velocity. Today the simulator exposes everything
needed (`_outputs`, `input_buffer`, `mem`, cycle count), but tests read raw
addresses — `mem[0x5800]`, `mem[0x4000]`, hand-built cell lists — instead of
expressing behavioural intent. Every new primitive (especially the
doc-#3 additions: `KEY-STATE`, `WAIT-FRAME`, `BEEP`, `KEMPSTON`,
`IM2-HANDLER!`) is effectively un-TDD-able until this lands.
**Difficulty:** medium. Mostly API design and a few simulator hooks; no
deep compiler work.

Goal: a public `zt.testing` module that makes assertions read like
behavioural specifications. A `WordHarness` that takes a snippet or a word
name, runs it in the simulator, and returns a rich result object with
semantic accessors rather than raw memory reads.

```python
result = harness.run_word("beep", stack=[100, 50])
result.stack == []
result.speaker_toggles > 0
assert_in_range(result.cycles, 40_000, 60_000)

result = harness.run_word("key", keys=b"A")
result.stack == [65]

result = harness.run("10 20 + dup *", stack=[])
result.stack == [900]

result = harness.run_word("plot", stack=[100, 50])
result.pixel_set(x=100, y=50)

result = harness.run_word("kempston", kempston=0b10000)
result.stack == [16]
```

**Implementation sequence** (each step is a prerequisite for the next):

1. **`WordHarness` + result facade.** Backed by the existing `ForthMachine`.
   No new simulator capabilities. Semantic accessors (`pixel_set`, `attr_at`,
   `char_at`, `border_writes`, `speaker_toggles`, `port_writes_to`, `stack`,
   `cycles`). `run_word(name, stack=[...])` and `run(snippet, stack=[...])`
   entry points. Snippet compilation caches the primitive dictionary image
   so per-test overhead stays low. This step alone covers roughly 80% of
   word-level TDD needs.

2. **Input scripting beyond `KEY`.** `keys=b"..."` already works through the
   existing hook. Add `kempston=bits` (hook port `$1F` reads) and a way to
   script per-frame input changes (`keys_by_frame=[b"A", b"", b"B"]`) for
   multi-frame tests.

3. **T-state-accurate cycle counting.** Opt-in flag
   (`WordHarness(cycle_accurate=True)`). Retrofit a T-states-per-opcode
   table into the simulator's dispatch. This unblocks testing anything
   whose correctness is a timing property: `BEEP`, border-race effects,
   any primitive that must fit in an interrupt window.

4. **Synthesized interrupts.** When `iff=True` and cycle-accurate mode is
   on, the simulator raises an interrupt every 69,888 T-states (one 50 Hz
   frame). Unblocks `WAIT-FRAME` and interrupt-handler TDD. `run_word`
   grows `max_frames=N` as an alternative stopping condition.

5. **Promote `zt.testing` to public API.** Document it. Add a short
   "how to TDD a Forth word" guide. Now external zt users can TDD their
   own game logic in the same idiom the compiler tests use.

**Known limitations to document up front.** Hardware addresses (`$4000`,
`$5800`) are physics, not zt choices — the facade hides them behind
`pixel_set` and `attr_at`, but they're still real. Cycle-accurate mode
models opcode timing, not memory contention or ULA-`OUT` interaction, so
precisely T-state-synchronised border effects may pass in simulation and
still glitch on hardware. Both worth calling out; neither is a blocker.

**Cross-cutting effect.** Most Tier 2–4 items below become significantly
cheaper to land once this exists, because each new primitive can be
TDD'd end-to-end rather than only byte-sequence-checked. That's the
reason it sits at #2 in Tier 1 rather than lower.

### 1.3 M8 — `.tap` output

Already planned in `PLAN.md` M8. Completing it unblocks "load on a real
Spectrum," which is the next thing every new user asks for after "does it
work on my phone emulator?"

**Impact:** high. Unblocks demos on real hardware.
**Difficulty:** low-medium. Well-specified format, small amount of code.

Deliverable: `zt build foo.fs -o foo.tap` produces a two-block `.tap` — a
header block naming the program, and a data block containing the memory image.
Include a tiny BASIC loader stub that `RANDOMIZE USR`s into the entry point.

### 1.4 Peephole expansion

**Impact:** medium-high (PLAN.md projected 15–25% speedup; current rules only
cover the obvious cases).
**Difficulty:** low per rule; each rule is 2–3 lines of Python.

Current rules (`peephole.py:DEFAULT_RULES`) — nine entries. Add:

- `DUP +` → `2*` (fused; saves one dispatch)
- `SWAP SWAP` → (eliminate)
- `DROP DUP` → `NIP` when the value isn't used — safe only for TOS-equal
  patterns, so narrow
- Constant folding: `n1 n2 +`, `n1 n2 AND`, `n1 n2 OR`, `n1 n2 XOR`,
  `n1 n2 LSHIFT`, `n1 n2 =`, `n1 n2 <` — all computable at compile time
- `LIT 0 =` → `0=` (already have `0=`, just not as a rewrite target)
- `LIT 0 <` → `0<`
- `OVER OVER` → `2DUP` ✓ (already have)
- `DUP ROT ROT` → stack-preserving pattern detection for later
- `SWAP OVER` → (eliminate when followed by operator — tricky)

Constant folding is the biggest leverage: an expression like `screen-start 32 * row + col +` collapses to a single `LIT` if all operands are known constants. This requires the peephole pass to track a small run of literals.

### 1.5 Native signed `/`, `MOD`, `/MOD`

**Impact:** medium (stdlib implementations in `stdlib/core.fs` are slow due
to double `U/MOD` + conditional negations).
**Difficulty:** low-medium. ~50 lines of Z80.

Today: `/MOD` in stdlib does four abs/negate operations around one `U/MOD` —
roughly 200 threaded dispatches per call. A native signed-restoring division
primitive is ~40 lines and ~400 T-states, an order of magnitude faster.

Keep the stdlib versions as a fallback for `--no-native-div` builds.

### 1.6 Tail-call compilation for last call in colon

**Impact:** medium. Shrinks every colon word by one dispatch, and makes
recursion stack-cheap.
**Difficulty:** low. Compiler pattern match.

When the last cell before `EXIT` in a colon body is a `ColonRef`, emit a
direct jump rather than a call + exit. This is a pure compiler transform in
`ir.resolve` or as an additional peephole rule on the cell stream.

---

## Tier 2 — Core quality

### 2.1 Frame-sync primitive and interrupt infrastructure

**Impact:** high. Enables consistent animation speed, audio timing, and
frame-based game logic — all four genres want this.
**Difficulty:** medium. Requires installing an IM 2 vector table and a
50 Hz tick counter.

Proposed primitives:

| Word | Effect | Notes |
|------|--------|-------|
| `WAIT-FRAME ( -- )` | Block until next frame interrupt | Needs IM hook |
| `TICKS ( -- n )` | Frames since boot | 16-bit counter |
| `TICKS! ( n -- )` | Reset counter | For benchmarks |
| `INT-ON ( -- )` / `INT-OFF ( -- )` | Gate interrupts |

The runtime must reserve a 257-byte aligned IM 2 vector table, install a
handler at a known address, and call `IM 2; EI` at program start. The
dispatch path currently uses `PUSH DE; RET` which briefly puts user data
where interrupts would push return addresses — the handler needs to be
tolerant of that, or dispatch must briefly `DI` on critical edges.

The existing `_outputs` capture in `sim.py` extends naturally to
instruction-count-based simulated interrupts.

### 2.2 Expand the inlining whitelist

**Impact:** medium (inlining already active, whitelist is currently 26
primitives).
**Difficulty:** low per addition. Main constraint is relocation safety.

Add to `INLINABLE_PRIMITIVES`: `2drop`, `2swap`, `rot`, `tuck`, `negate`,
`min`, `max`, `xor`, `rshift`, `u_less`. Each requires verifying that the
primitive body has no absolute addresses (`has_absolute_jump_in_body` already
tests this).

`min`, `max`, `abs` — these use conditional forward jumps (`jp_z _abs_done`)
that make them relocation-unsafe. Rewriting them to use `JR` with short
displacements (< 127 bytes) would allow inlining and save dispatches on every
comparison.

### 2.3 Dead-code elimination

**Impact:** medium. Every unused `:` definition costs 2 bytes per referenced
primitive plus its body.
**Difficulty:** medium. Requires a reachability pass from entry points
(`main` and anything marked `export`).

Walk the IR graph from entry points, mark reachable words, drop the rest
from the image. Peephole already has the infrastructure to iterate over
cells; this is a pre-emission garbage collection pass.

Saves typically 5–15% of image size on library-heavy programs.

### 2.4 Control-stack tagging for better errors

**Impact:** medium. Currently a mismatched `WHILE` / `REPEAT` / `LOOP`
produces a confusing message.
**Difficulty:** low. The tag machinery is sketched in `PLAN.md` M4.

Tag each control-stack entry (`"if"`, `"begin"`, `"do"`). On pop, assert the
tag matches what the closing word expects. Surface the token location in the
error.

### 2.5 Profiler integration in the CLI

**Impact:** medium. `profile.py` exists but isn't reachable from `zt`.
**Difficulty:** low. Wire it into the simulator + CLI.

Add `zt profile source.fs --ticks 1000000` that runs the compiled image in
the simulator, samples the PC, and prints a word-level profile report.
Cheap wall-clock win because `profile.py` already does the hard part.

---

## Tier 3 — Reach

### 3.1 Compile-time evaluation of constant expressions

**Impact:** medium-high. Idiomatic Forth relies heavily on constants like
`SCREEN-WIDTH 24 * CELLS` which currently compile to a sequence of
dispatches.
**Difficulty:** medium. Needs a host-side mini-interpreter for a subset of
primitives.

This is the natural extension of peephole constant folding: instead of only
matching two-literal patterns, run a host-side partial evaluator over a
window of IR cells and replace it with a single literal whenever all inputs
are literals.

Scope it to pure primitives (no `EMIT`, no `@`), and the implementation
reduces to a lookup table from primitive name to a Python lambda.

### 3.2 Inline-next control for colon words

**Impact:** medium. The current global `inline_next` toggle is binary;
selective inlining would save code size on cold paths.
**Difficulty:** medium. Requires annotating words with expected call
frequency.

Add `: foo ... ; COLD` and `: foo ... ; HOT` attribute words. `COLD` words
get a non-inlined `JP NEXT`; `HOT` (default) gets the inlined version. Most
code stays HOT; large one-shot initialization gets COLD to save bytes.

### 3.3 String pool deduplication

**Impact:** low-medium. `." HELLO"` compiled twice stores the string twice.
**Difficulty:** low. `string_pool.py` already exists; just needs a hash-based
lookup on insert.

### 3.4 `VARIABLE` / `CREATE` / `ALLOT` improvements

**Impact:** medium. Larger programs (adventures with world state) need more
data-space primitives.
**Difficulty:** low-medium.

Add `BUFFER: name size`, `CONSTANT`, `VALUE`, and a clean `ALLOT` that
reserves bytes at `HERE`. Wire the dictionary's data-space cursor into
the compiler's existing origin tracking.

### 3.5 `SEE` word — source-level decompiler in-image

**Impact:** low. Only useful when someone ports a REPL later.
**Difficulty:** low-medium. Most of the logic is in `inspect.py` already.

Exposes the decompiler as a word that's callable from within a REPL, so
users can inspect their own definitions at "runtime" (in the simulator).

---

## Tier 4 — Hardware frontier

### 4.1 M9 — 128K banking

**Impact:** high for any non-trivial game. 48K gets tight fast once you add
level data and audio.
**Difficulty:** high.

Requires: detecting 128K at runtime (test port `$7FFD` behaviour), a
bank-switching primitive (`BANK ( n -- )`), a cross-bank call convention,
and a build-time flag that targets 128K and picks a page layout.

Related: M9 in PLAN.md covers this at a planning level.

### 4.2 AY-3-8912 sound driver

**Impact:** high for games. The beeper is a feasible short-term fallback
(Tier 3.6 below), but music wants AY.
**Difficulty:** high.

Three components:
- Low-level primitives: `AY! ( val reg -- )`, `AY@ ( reg -- val )`
- A driver that runs from the interrupt handler — reads a compact tune
  format, updates AY registers each frame
- Compile-time tune data format (could be imported from `.vtx`, `.psg`, or
  a custom Forth-friendly pattern format)

Graceful-degradation plan: ship a `SOUND` primitive that dispatches to
either beeper (Tier 3.6) or AY at runtime based on detected hardware.

### 4.3 Beeper primitive (48K graceful degradation)

**Impact:** medium. Unblocks audio on 48K.
**Difficulty:** medium. ~60 lines of cycle-counted Z80.

```
BEEP ( duration pitch -- )
```

Classic Spectrum beeper loop: toggle bit 4 of port `$FE` at a cycle-counted
interval. Duration in frames, pitch as a Z80 half-period in T-states. Runs
with interrupts disabled so timing is deterministic.

Not polyphonic, can't play while running game logic — but sufficient for
blip, tone, crude music.

### 4.4 TR-DOS / divMMC save primitives

**Impact:** medium. Text adventures benefit most.
**Difficulty:** high. Interface is hardware-specific.

Probably one level of abstraction: `SAVE-BLOCK ( addr len filename -- ok )`
that dispatches to divMMC hook calls when divMMC is present, falling back
to screen-based "write this down" output otherwise.

---

## Tier 5 — Developer experience

### 5.1 Release on PyPI

**Impact:** high for adoption, zero for existing users.
**Difficulty:** trivial. `pyproject.toml` and `dist/` are already in place.

`pip install zt-forth` for anyone who isn't cloning the repo.

### 5.2 Better error messages

**Impact:** medium. Most errors currently say "unexpected word 'X' in
interpret state" with a source location, which is accurate but not helpful.
**Difficulty:** low. Case-by-case.

Add suggestions: "did you mean `dup` (defined) or `2dup` (defined)?" when an
unknown word is close to a known one. Surface the enclosing `:` definition
name in compile-state errors.

### 5.3 `zt run` subcommand

**Impact:** medium. Current flow requires building a `.sna` and opening it
in an emulator.
**Difficulty:** low. The simulator already runs the compiled image.

`zt run source.fs --input "ABC" --ticks 1000000` compiles, runs in sim,
prints the resulting screen + stack + border writes as text. Makes the tight
development loop trivial.

### 5.4 Step debugger in the simulator

**Impact:** medium. When tests fail, "what's on the stack at line 23" is
currently a print-and-rebuild dance.
**Difficulty:** medium.

Expose `Z80.step()` + source map lookup as a pytest fixture. `dbg.until("draw")`, `dbg.step()`, `dbg.stack()` helpers.

### 5.5 Language server

**Impact:** low-medium. Syntax highlighting in editors would be pleasant.
**Difficulty:** medium.

A minimal LSP for Forth: completion from the dictionary, go-to-definition
from `.fsym`, hover for stack effects (parsed from `( ... )` comments). Ship
as `zt lsp` subcommand.

### 5.6 Documentation site

**Impact:** medium for adoption.
**Difficulty:** low. Most of the content exists in `primitives.md`, `PLAN.md`,
and the forthcoming docs.

mkdocs or Quarto against the current markdown files. Host on GitHub Pages.

### 5.7 CI

**Impact:** medium.
**Difficulty:** trivial.

GitHub Actions running `uv run pytest` on push. Publish coverage, catch
regressions. No reason not to have this; just hasn't been wired up.

### 5.8 Fuzz testing

**Impact:** low-medium.
**Difficulty:** low. Hypothesis + existing IR roundtrip.

Property tests: round-trip cells to JSON and back, round-trip Asm
compile/decompile, random Forth programs shouldn't crash the compiler.
`hypothesis` integrates cleanly with `pytest`.

---

## Tier 6 — Speculative

### 6.1 Subroutine-threaded or direct-threaded mode

ITC is fast enough for most things but STC would double inner-loop speed at
~2× code size. Could be a compile flag. Interesting because the IR is already
abstract over the execution model.

### 6.2 Multi-target: MSX, Amstrad CPC, CP/M

All three are Z80, all three have different ROM conventions and screen
layouts. A `--target` flag plus per-target `stdlib/` module could share 90%
of the compiler. Low priority unless a user actually asks.

### 6.3 FFI to `.o` files or `.asm` imports

`ASM: name ... ;ASM` that accepts raw Z80 mnemonics. Already technically
possible through the `Asm` class but not exposed at source level.

### 6.4 A REPL that runs on-target

A persistent simulator session with a tokenizer that accepts user input and
compiles-and-runs incrementally. Classic Forth feature; requires more of the
dictionary machinery to be runtime-accessible rather than compile-time-only.

### 6.5 Self-hosting

The compiler written in Forth, running in itself. Iconic Forth goal. Large
project (needs file I/O, proper error recovery, the full immediate-word
mechanism at runtime). Treat as a 5-year aspiration, not a plan item.

---

## Cross-cutting observations

Three themes run through the tiers above and are worth calling out:

**Real hardware is the honest target.** Tier 1 (`.tap`, real `KEY`) and
Tier 4.3 (beeper) together take zt from "lovely simulator" to "can ship a
demo to a Spectrum user." Nothing above Tier 2 matters much until that works.

**The IR is the right abstraction to exploit.** Constant folding, dead-code
elimination, tail-call, inlining expansion, and the language server all
operate on the same `list[Cell]` representation. The existing code is clean
here; building on it is cheap.

**Test infrastructure is the leverage point.** The simulator + pytest
combination means behavioural tests are *possible* today; once §1.2 lands,
they become *convenient*. Most tier-2–4 items above become significantly
cheaper to land with a word-level testing facade in place, because every
new primitive can be TDD'd end-to-end without touching a real Spectrum.
