# Changes

## IM 2 handlers can now be plain `:` colon words

`IM2-HANDLER!` previously took a raw Z80 entry-point address; the user had to
hand-roll a `:::` body that saved registers, did the work, and ended in
`EI; RETI`. This is now a built-in.

**New surface.** `IM2-HANDLER! ( xt -- )` takes the xt of a colon word.
Three new primitives back it:

- **`__im2_shim__`** — Z80-level prologue/epilogue. Saves
  AF/HL/BC/DE/IX/IY on entry, dispatches into the handler thread,
  finishes through `__im2_exit__`. Pointed at by the JP slot at `$B9BA`
  every time `IM2-HANDLER!` runs.
- **`__im2_exit__`** — primitive reached after the user word's EXIT
  dispatches the second cell of the thread. Restores the saved state
  and ends with `EI; RETI`.
- **`__im2_thread__`** — 4-byte mutable thread. Cell 0 holds the user
  xt (written by `IM2-HANDLER!`). Cell 1 holds the xt of `__im2_exit__`
  (resolved at link time).

**Cost.** ~140 T-states of overhead per fire on top of the user body.
0.2% of CPU at 50 Hz. The shim, exit primitive, and thread total ~30
bytes, all gated by liveness when `IM2-HANDLER!` itself is dead.

**User constraint.** The colon word must be stack-neutral (`( -- )`) on
both the data and return stacks. The shim doesn't swap to a private SP.

**Breaking change.** `IM2-HANDLER!`'s signature is now `( xt -- )`,
not `( addr -- )`. Code that previously installed a raw `:::` ISR via
`IM2-HANDLER!` no longer works — the shim adds 6 register pushes the
old ISR's manual `EI; RETI` doesn't account for. Two existing demos
(`examples/im2-rainbow`, `examples/im2-music`) are migrated. Power
users wanting the raw path emit a `:::` ISR and patch the JP slot
operand at `$B9BA` directly.

**Demo size.** The motivating case shrank dramatically:

```forth
\ before — :::-Z80 inside the rainbow demo
::: rainbow-isr
    push_af
    ' border-tick ld_a_ind_nn
    inc_a  7 and_n
    $FE out_n_a
    ' border-tick ld_ind_nn_a
    pop_af  ei  reti ;

\ after — plain Forth
: rainbow-isr
    border-tick @ 1+ 7 and  dup border-tick !  border ;
```

The AY-music demo's 50-line `:::` ISR became three composed colon words
(`cycle-border`, `advance-tick`, `current-period play-channel-a`),
each individually unit-testable.

## Tests

- New: `tests/test_im2_colon_isr.py` — 8 end-to-end tests covering the
  colon-word path, including nested calls and a busy foreground.
- Updated: `tests/test_primitives_im2.py` — byte-level tests rewritten
  for the new 20-byte `IM2-HANDLER!` body and the thread-based fetch.

4463 / 4463 green.

## Documentation

- `docs/im2-architecture.md` — moved Forth-level ISRs out of "non-goals"
  into a "Shipped after v1" section that describes the shim and trade-offs.

---

# Earlier changes

Three new Z80 primitives for 2-bit-quantized neural network kernels (z80ai-style),
plus the simulator and opcode-table additions they needed.

## New primitives

- **`UNPACK-NIBBLES ( byte -- hi lo )`** — split byte into two unsigned nibbles.
- **`UNPACK-2BITS ( byte -- u3 u2 u1 u0 )`** — split byte into four unsigned 2-bit
  fields, LSB-first packing (matches z80ai's `buildz80tap.py`).
- **`2BITMULADD ( raw act addr -- )`** — signed-2-bit multiply-add into a 16-bit
  cell. Maps raw 0..3 to weight {-2,-1,0,+1} and applies `*addr += weight*act`
  via 4-way branch, never invoking general 16x16 multiply.
- **`2BIT-DOT+! ( wptr aptr count addr -- )`** — accumulating dot product over
  `count` weights. Application-specific kernel, lives in core for now.

All four are registered in `PRIMITIVES`. Of these, only `UNPACK-NIBBLES` is on
the `INLINABLE_PRIMITIVES` paste whitelist:

- `UNPACK-NIBBLES` — 12 bytes, no jumps. ✓
- `UNPACK-2BITS` — 30 bytes; exceeds the 20-byte size policy. Off whitelist.
- `2BITMULADD` — uses absolute `jp_m` for the negative branch, relocation-unsafe.
  Off whitelist (same category as `abs`, `min`, `max`, `less_than`).
- `2BIT-DOT+!` — internal loop with `call`/`ret`. Off whitelist.

The three off-whitelist primitives still work fine inside `::` bodies — they're
called via normal NEXT dispatch, not pasted. Profile shows this is performant:
`mac4-fast` calls `2BITMULADD` from inside `::` and lands at 592 T-states/MAC.

## Opcode table additions

`src/zt/assemble/opcodes.py`: `sbc_a_d`, `ld_ind_nn_hl`, `ld_hl_ind_nn`,
`ld_bc_ind_nn`, `ld_ind_nn_bc`, `ld_a_ind_bc`, `ld_d_a`.

## Simulator additions

`src/zt/sim.py`: handlers for `0x22`, `0x2A`, `0x0A`, `ED 4B`, `ED 43`.

## Tests

- `tests/test_unpack_primitives.py` (80 tests)
- `tests/test_2bit_muladd.py` (24 tests)
- `tests/test_2bit_dot_plus_store.py` (20 tests)

124 / 124 green.

## Profile results (zlm-smoke)

A 32-MAC row (8 packed bytes × 4 weights) against 16-bit activations:

```
                          T-states/MAC    sec/char (32K MACs @ 3.5MHz)
threaded mac4                4,018          ~37 sec
::-fused mac4-fast (* +!)    1,292          ~12 sec
::-fused mac4-fast (2BMA)      592          ~5.4 sec
2BIT-DOT+! (whole row)         251          ~2.3 sec
```

## Examples

- `examples/zlm-smoke/main.fs` — profiling harness comparing threaded MAC,
  `::`-fused MAC, and full-row `2BIT-DOT+!`. Profile-only; black screen.
- `examples/zlm-layer/main.fs` — **tier (A) demo, runnable.** A 32-input × 4-output
  linear layer with random fixed weights and activations (Python `random.seed(42)`).
  Computes `outputs[i] = ReLU(dot(weights[i], activations))` using `2BIT-DOT+!`,
  prints results via `at-xy` and `.` Expected screen content:

  ```
  zlm-layer demo (32x4)
  expected: 377 1135 190 1175

  out 0 : 377
  out 1 : 1135
  out 2 : 190
  out 3 : 1175
  ```

  Build: `uv run python -m zt.cli build examples/zlm-layer/main.fs -o build/zlm-layer.sna`
  Drop the .sna into FUSE or ZEsarUX. End-to-end test in `tests/test_examples_zlm_layer.py`
  asserts all four numbers appear on screen in order.

## Files in this zip

```
CHANGES.md
src/zt/assemble/inline_bodies.py
src/zt/assemble/opcodes.py
src/zt/assemble/primitives.py
src/zt/sim.py
tests/test_unpack_primitives.py
tests/test_2bit_muladd.py
tests/test_2bit_dot_plus_store.py
tests/test_examples_zlm_layer.py
examples/zlm-smoke/main.fs
examples/zlm-layer/main.fs
```

Drop them into your zt tree at the matching paths to apply.

# Tree-shaking foundation (in progress)

Liveness-driven image emission. **Status: integrated into CLI; supports most
real-world programs.** Remaining lifts are `'`/`[']` (word-address-as-immediate),
banking, and native control flow.

## What's in

**Phase A — pure liveness analysis** (`zt.compile.liveness`):
- `compute_liveness(roots, bodies, prim_deps) -> Liveness` with `(words, strings)`
  frozensets.
- Walks IR cells (`PrimRef`, `ColonRef`, `Literal`, `Branch`, `StringRef`,
  `Label`) and primitive dep graph from a worklist of roots. Cycle-safe.

**Phase B.1 — primitive blob harvesting** (`zt.assemble.primitive_blob`):
- `harvest_primitive(creator, *, inline_next)` runs a `create_*` function into a
  throwaway `Asm` and captures `(label_offsets, code, fixups, rel_fixups,
  external_deps)`. `external_deps = referenced - declared` correctly classifies
  trailing data (`_emit_cursor_row`, `_spr_sp`, `_key_table`, …) as internal.
- `emit_blob(asm, blob)` splats a harvested blob into a target `Asm` —
  byte-identical to running the creator directly. Tested across the full
  PRIMITIVES set with `inline_next=True` and `=False`.
- `BlobRegistry.from_creators(creators)` is the single source of truth for
  blob metadata; replaces the redundant double-harvest in
  `_build_creators_by_name`. `forth_visible_creators()` matches the existing
  `_creators_by_name` keyset exactly (109 keys).

**Phase B.2 — wired into Compiler** (`zt.compile.compiler`):
- `_register_primitives` collapsed from two passes to one via `BlobRegistry`.
- `_build_creators_by_name` deleted.
- `Compiler.compute_liveness()` reports the live word/string set for the
  current state. Roots: `["main", "halt", "next", "docol"]`. Image is unchanged.

**Phase B.3 — actual tree-shaking** (`zt.compile.tree-shaking`):
- `Compiler.build_tree_shaken() -> (image, start_addr)` constructs a fresh image
  containing only live primitives, colons, strings, constants, variables, and
  `create` definitions. Re-emits colon bodies via `ir.resolve()` against a
  freshly-allocated address table; re-synthesises constant/variable shims and
  copies their data bytes verbatim from the eager image.
- **Build-tree-shaken commits state**: after the call, `compiler.asm` holds the
  tree-shaken image, `compiler.words[*].address` and `_start` reflect new addresses,
  and dead user words are dropped from the dictionary. CLI/debug-artifact
  writers (`write_map`, `write_sld`, `write_fsym`, profile) just work
  unmodified. Added `Dictionary.__delitem__` to support pruning.
- Supports: colons, literals, branches, control flow (if/then, begin/until,
  do/loop), strings (`s"`, `."`), constants, variables, `create`, `,`, `c,`,
  `allot`.
- Raises `NotImplementedError` for: `'` (word-address-as-data),
  `[']` (word-address-as-literal), banking (`in-bank`), native control flow.
  Compiler now tracks `_uses_word_address_data` / `_uses_word_address_literal`
  flags so the rejection is exact rather than reactive.
- Word-address dict is canonical lowercase (the dictionary convention); the
  earlier mixed-case workaround in `_blob_is_live`/`_primitive_addrs` collapsed.

**Phase B.3 — CLI integration** (`zt.cli.main`):
- `zt build --tree-shake source.fs -o out.bin` produces an tree-shaken image.
- `--tree-shake` is opt-in; default behavior remains byte-identical to the eager
  build (no surprises).
- Programs using `'`/`[']`/native that pass `--tree-shake` exit with a clear
  `error: --tree-shake does not yet support this program: …` and a non-zero status.

**Real-program savings** (`zt build --tree-shake` on stdlib-included programs):
- hello: 4147 → 1011 bytes (75.6% smaller)
- sierpinski: 4100 → 943 bytes (77.0% smaller)
- plasma4: 4491 → 1661 bytes (63.0% smaller)
- reaction: 4541 → 2009 bytes (55.8% smaller)
- mined-out: 15136 → 12316 bytes (18.6% smaller)
- **zlm-tinychat-48k: 40315 → 39467 bytes (848 B saved → 9.4× headroom**:
  101 → 949 bytes between image-end and the `acts2` buffer at $F9E0). Same
  HELLO→HI behavior verified on the Z80 simulator under `@pytest.mark.slow`.

## Bug surfaced and fixed: tinychat-48k return-stack budget

While instrumenting `zlm-tinychat-48k` for tree-shaking validation, peak return-
stack usage during a HELLO query measured at **26 bytes** — leaving only
**6 bytes (3 cells) of margin** before stack frames would overflow into the
`acts1` buffer ($FD60..$FF60), the network's last hidden activation. With
deeper queries this margin would silently corrupt model state, producing
garbage output and (depending on what got overwritten) program resets on
real hardware.

**Fix**: the original layout left an unused 32-byte gap between rstack-top
($FF80) and dstack-floor ($FFA0). Bumping `--rstack 0xFF80 → 0xFFA0`
consumes the gap, doubling the rstack budget to 64 bytes and raising the
acts1-margin from 6 → 38 bytes — at zero image cost, no model change, no
data-stack impact. New regression test `test_rstack_peak_within_budget`
runs the simulator and pins both peak usage (≤32) and acts1 margin (≥16),
so future increases in stack pressure fail the test rather than silently
corrupting model state.

This bug was orthogonal to tree-shaking (would have manifested in the eager
build too, given a sufficiently deep input), but tree-shaking-driven probing
made the tight margin visible.

## Bug surfaced and fixed: `_start` did not disable interrupts

Even with the rstack widened, real-hardware tinychat-48k still reset on any
input. Diagnosis: with `--origin 0x5C00`, the image overlaps the Spectrum
system-variables area `$5C00..$5CB6`. The `R>` primitive's body lives at
`$5C77..$5C84`, including bytes at `$5C78..$5C7A` — exactly where the ROM's
IM 1 interrupt handler increments the `FRAMES` timer every 1/50 second.

If interrupts are enabled when the program starts, every interrupt
overwrites three bytes of `R>` with the timer value. The next `R>` call
executes garbage instead of `LD L,(IY+0); LD D,(IY+1); ...` and the
program crashes — typically as a reset, because the corrupted bytes form
some random control-flow instruction that lands at $0000 or some bad
address.

`.sna` snapshots are supposed to load with interrupts disabled (IFF2=0 in
the header), but in practice many loaders, BASIC entry trampolines, and
emulator paths leave interrupts enabled. The simulator never executes
interrupts at all, so this corruption was completely invisible to tests.

**Fix**: `_emit_threaded_start`, `_emit_native_start`, and the tree-shaking
`_emit_start` now all begin with `DI`. Programs are defensive against any
caller's interrupt state. `WAIT-FRAME` already does its own `EI`/`HALT`/`DI`
dance, so existing programs that need frame-synced timing keep working;
the rest run faster and are robust against the real-hardware reset bug.
New regression test `tests/test_start_di.py` pins `0xF3` as the first byte
of `_start` for both threaded and native modes, in both `build()` and
`build_tree_shaken()`.

The 128K tinychat doesn't hit this because its default origin is `$8000`,
in clean RAM far from the system variables area.

## Bug surfaced and fixed: DI alone wasn't enough — origin moved past sysvars

After landing the DI fix, `tc48d.sna` continued resetting on real hardware
the moment the user pressed Enter on a non-empty query. Border-colour
instrumentation localised the crash to "BLUE → typed letter → RED → Enter
→ reset", with empty Enter not crashing — pinpointing the entry into
`chat`. Address comparison between the eager and tree-shaken builds revealed
the pivotal layout difference: in the eager image the byte at `$5C78`
(FRAMES timer) lay inside `R>` primitive code; in the tree-shaken image it lay
inside `1+`, where the IM 1 corruption pattern happened to be benign for
the chat call path.

The simulator was modified locally to fire a synthetic IM 1 (incrementing
`$5C78` every ~70K t-states) and the eager build deterministically died
at "unimplemented opcode 0xFF at 0x5C78" — direct evidence that the
corruption story was correct. The same simulated IM 1 against an tree-shaken
build with origin moved to `$5CB6` ran cleanly to completion and answered
HELLO with HI even after FRAMES had been incremented several hundred
times.

**Why DI in `_start` wasn't sufficient**: some loaders re-enable
interrupts during SNA load, allowing one or more interrupts to fire in
the few microseconds between `RETN`-to-program-PC and the program's `DI`
executing. Even one IM 1 fire is enough to corrupt `$5C78` if it sits
inside live primitive code.

**Fix**: the recommended build for `zlm-tinychat-48k` is now
`--origin 0x5CB6 --tree-shake`. `$5CB6` is the byte immediately past the
Spectrum 48K system-variable area, so any FRAMES corruption lands in
unallocated RAM that the program never reads or executes. Tree-shaking
is required because the eager image (40 316 B) doesn't fit between
`$5CB6` and the `acts2` buffer at `$F9E0`; the tree-shaken image (39 468 B)
fits with 766 B of margin.

Test coverage: `test_origin_clears_system_variables` (fast; pins origin
≥ `$5CB6`) and `test_survives_simulated_im1_corruption` (`@pytest.mark.slow`;
runs the production build under the synthetic IM 1 loop and asserts that
HELLO still produces HI). The eager-only path tests
(`test_image_ends_below_acts2`, `test_buffer_outside_image`) were
rewritten against the tree-shaken image since the eager build no longer fits
at the production origin.

## Auto-tree-shake-when-possible: tree-shaking is now the default

`zt build` now auto-tree-shakes by default. Programs that tree-shake cleanly get
the savings transparently; programs using features the tree-shaker
doesn't yet support (`'`, `[']`, or `in-bank` compile-time banking) fall
back to the eager build with a single warning to stderr. The new flag
matrix is:

* (no flag, default) — try tree-shake; fall back to eager with a warning if
  the program uses unsupported features. Best of both worlds: every
  supportable program gets the savings, no existing build breaks.
* `--tree-shake` (strict) — try tree-shake; **fail loudly** on unsupported
  features rather than fall back. For users who want to be sure they're
  shipping the smallest possible image and would rather know at build
  time when something prevents tree-shaking.
* `--no-tree-shake` — force the eager build, regardless of whether tree-shaking
  would have worked. Useful when downstream tooling depends on a
  specific address layout.
* `--tree-shake` and `--no-tree-shake` are mutually exclusive — argparse rejects
  the combination with a clear error.

The fallback path also picks up a new banking-rejection guard
(`_reject_unsupported_features`): in-bank/end-bank programs would
previously crash inside `_next_boundary_after`; they now raise
`NotImplementedError("banked code is not yet supported")` — caught by
the auto-tree-shake loop and reported as a clean fallback.

**Survey across all 24 examples** (`tools/tree-shaking_survey.py`): total
image size shrinks from 157 956 B → 101 144 B (36 % reduction). 19 of
24 examples get the savings; 5 fall back to eager (`sprite-demo`,
`shadow-flip`, `bank-table`, `zlm-emit-test`, `zlm-tinychat`). Per-
example reductions for the tree-shake-supported set range from 18 % to 95 %:

| example              | eager    | auto-tree-shake | saved   | %      |
|----------------------|----------|------------|---------|--------|
| counter              |    3 967 |        178 |   3 789 |  95.5% |
| sierpinski-3         |    4 024 |        500 |   3 524 |  87.6% |
| sierpinski-2         |    4 074 |        795 |   3 279 |  80.5% |
| bank-rotator         |    4 152 |        850 |   3 302 |  79.5% |
| sierpinski (file)    |    4 032 |        623 |   3 409 |  84.5% |
| plasma2              |    4 199 |        927 |   3 272 |  77.9% |
| sierpinski (dir)     |    4 091 |        952 |   3 139 |  76.7% |
| hello                |    4 140 |      1 038 |   3 102 |  74.9% |
| plasma-128k          |    4 282 |      1 081 |   3 201 |  74.8% |
| plasma               |    4 190 |      1 064 |   3 126 |  74.6% |
| zlm-smoke            |    4 632 |      1 363 |   3 269 |  70.6% |
| plasma3              |    4 390 |      1 413 |   2 977 |  67.8% |
| plasma4              |    4 476 |      1 664 |   2 812 |  62.8% |
| zlm-layer            |    4 369 |      1 774 |   2 595 |  59.4% |
| zlm-multilayer       |    4 686 |      2 022 |   2 664 |  56.9% |
| reaction             |    4 524 |      2 026 |   2 498 |  55.2% |
| zlm-trigram          |    7 680 |      5 325 |   2 355 |  30.7% |
| mined-out            |   14 901 |     12 147 |   2 754 |  18.5% |
| zlm-tinychat-48k     |   41 213 |     39 468 |   1 745 |   4.2% |

Tests: `tests/test_cli.py::TestCliTreeShake` rewritten end-to-end to pin
the new contract — defaults auto-tree-shake and produce identical bytes to
explicit `--tree-shake`; `--no-tree-shake` reproduces the legacy eager build;
default falls back silently for unsupported programs with a stderr
warning; explicit `--tree-shake` still fails strictly. `--inline-primitives`
testing was retargeted at `--no-tree-shake` because it's an eager-pipeline
optimization (tree-shaking rebuilds colon bodies fresh against a new
primitive address table, which bypasses the inline-primitives splice).

## Bugs surfaced (not yet fixed)

- `_build_creators_by_name` historically excluded 13 primitives whose
  `external_deps` referenced data labels in *other* blobs (e.g. `at-xy` →
  `_emit_cursor_row` lives in `create_emit`'s blob). This means `::at-xy`
  (force-inline colon redefinition over a primitive) silently fails today.
  `BlobRegistry.forth_visible_creators` matches the buggy behavior
  intentionally — the right time to fix is when supporting trailing-data
  blobs uniformly via blob emission.
- `ZT_VERIFY_IR=1` exposes a pre-existing IR/bytes mismatch in `mined-out`
  (188 errors on `tests/test_examples_mined_out.py`). Not caused by this work.

## Remaining lifts

In priority order:

1. **`'` and `[']` (word-address-as-data and word-address-as-literal)** — both
   embed a word's address as an immediate value, indistinguishable from any
   other integer. Two options: (a) introduce `WordAddrLiteral` IR cell that
   resolves at emit time; (b) instrument `,` to record per-data-byte symbolic
   provenance and rewrite during data extraction. (a) is cleaner.
2. **Banking (`in-bank` / `end-bank`)** — separate `Asm` per bank;
   `_bank_asms: dict[int, Asm]` would each need its own emit pass.
3. **Native control flow** — bypasses the IR pipeline entirely. Native mode
   may stay outside tree-shaking for the foreseeable future.

## Test surfaces added

- `tests/test_liveness.py` (21)
- `tests/test_primitive_blob.py` (22)
- `tests/test_emit_blob.py` (13)
- `tests/test_blob_registry.py` (16)
- `tests/test_compiler_blob_registry.py` (9)
- `tests/test_build_tree_shaken.py` (33, including post-state, canonical-case,
  halting-program parity on sierpinski, and compile-and-shrink coverage on
  plasma4/reaction/mined-out)
- `tests/test_cli.py::TestCliTreeShake` (4 — flag works, smaller image, runnable
  .sna, clear error on unsupported features)
- `tests/test_examples_zlm_tinychat_48k.py` (4 new — image size below acts2,
  ≥500 B headroom, `@pytest.mark.slow` HELLO→HI parity)

All passing. Full focused suite: 807 tests green; full compiler-adjacent +
end-to-end stays green.


