# Native backend

`zt build --native` and `zt test --native` generate plain Z80 from the compiler's IR
instead of threaded cells walked by NEXT. It is experimental and opt-in; the threaded
build is still the default and is the oracle the native backend is tested against.

## Measured

`uv run python tools/bench_native.py <files>` builds both ways, runs both in the
simulator, checks the data stack, screen memory and port writes are identical, and
prints T-states and image size (threaded column is the tree-shaken build).

| Program | Threaded T | Native T | Speedup | Image |
|---|---|---|---|---|
| `tests/benchmarks/sieve.fs` | 9,536,609 | 2,593,961 | 3.68x | 88% |
| `tests/benchmarks/fib.fs` | 9,920,464 | 2,805,163 | 3.54x | 37% |
| `tests/benchmarks/gcd.fs` | 20,122,019 | 5,444,993 | 3.70x | 46% |
| `tests/benchmarks/bubble.fs` | 14,839,181 | 2,967,765 | 5.00x | 78% |
| `examples/reaction/bench.fs` | 8,520,766 | 2,466,559 | 3.45x | 90% |
| `examples/sierpinski/main.fs` | 3,244,764 | 1,228,351 | 2.64x | 64% |
| `examples/arkanoid/main.fs` (to first HALT) | 30,124,474 | 8,360,174 | 3.60x | 108% |

Programs that spend their time inside one big primitive (tinychat's dot product, the
blitters) gain little: the primitive bodies are the same bytes in both builds.

## Model

Register roles are unchanged, so every primitive body is reused as written:

| | |
|---|---|
| `SP` | data stack |
| `HL` | top of stack |
| `IY` | return stack |
| `IX` | link register (was the threaded IP) |

**Primitives.** Each `create_*` is re-harvested with `Asm(linked=True)`, where
`dispatch()` emits `JP (IX)`. A primitive is spliced inline at the call site when it
has one exit, refers to nothing outside its own body, does not touch IX and is at most
`INLINE_BYTE_LIMIT` (12) bytes; `(do)` is always inlined. Everything else is emitted
once and reached with `LD IX,ret / JP prim` (32 T round trip against NEXT's 79 T).
Splicing re-assembles the creator at the splice address, so bodies with internal
absolute jumps (`abs`, `min`, `<`) inline correctly.

**Colon words** are reached by `CALL`. The return address lands on the data stack, so
each word moves it somewhere else on entry. Whole-program analysis picks the cheapest
place that is safe:

| Convention | Used when | Entry | Return | Round trip |
|---|---|---|---|---|
| leaf | the word calls nothing | `POP IX` | `JP (IX)` | 39 T |
| static | it calls something but cannot be re-entered | `POP BC / LD (slot),BC` | `slot: JP nnnn` | 57 T |
| frame | it can be re-entered | push on `IY` | pop from `IY`, `PUSH DE / RET` | 164 T |

A word can be re-entered if it is in a call-graph cycle, can reach `EXECUTE`, or — when
the image uses IM 2 — is reachable from any word whose xt is taken. Threaded
call + return costs about 430 T.

**Small leaves are pasted.** A colon of at most `SMALL_LEAF_CELL_LIMIT` (10) cells that
calls nothing and exits only at its end is copied into its callers with fresh branch
labels. If nothing else needs it, it is not emitted at all.

**Everything NEXT used to interpret is code.** Literals are `PUSH HL / LD HL,nn`;
`0branch` is `LD A,H / OR L / POP HL / JP Z`; loops are inline; variables and constants
are literal pushes with no 7-byte shim; the fused `(@abs)` family becomes
`LD HL,(nn)` and friends. `EXECUTE` is `EX DE,HL / POP HL / CALL __execute__`, and the
xt of a primitive, variable or constant points at a generated one-cell wrapper colon.

**IM 2.** `interrupts.py` replaces the threaded shim/thread/exit trio with a shim that
saves the registers (IX included), `CALL`s the handler xt and returns with `EI / RETI`.

## Where the code is

| | |
|---|---|
| `compile/native/primitives.py` | linked harvest, inline decision, `:::` relinking |
| `compile/native/resolve.py` | what a `PrimRef` becomes |
| `compile/native/analysis.py` | call graph, re-entrancy, convention choice |
| `compile/native/expand.py` | pasting small leaves |
| `compile/native/plan.py` | which bodies are emitted, xt wrappers |
| `compile/native/emitter.py` | one colon word → Z80 |
| `compile/native/image.py` | layout, tick patching, dictionary commit |
| `compile/native/interrupts.py` | native IM 2 shim |

Tests: `test_native_*.py`, `test_cli_native.py`, `test_shadowed_definitions.py`. Every
`test-*` word in every `test_*.fs` is also collected as `<word>[native]`.

## What differs from the threaded build

- **Layout.** Addresses of code and data move. A program that depends on where a table
  lands will notice: `examples/voxel-letter` skips the carry when indexing `mask-table`
  and breaks when the table straddles a page, which it does natively
  (`test-plot-each-row-independent[native]` is an expected failure for that reason).
- **The return address is not on the return stack** in leaf and static words, so tricks
  that pop it with `r>` do not work. Balanced `>r … r>` is fine.
- **`HALT` inside a word** is just the instruction; after an interrupt execution
  continues with the next word instead of falling into the following primitive.
- **Code must run from RAM**: static words patch their own return jump.
- **Dictionary after `build_native()`**: emitted colons, variables and out-of-line
  primitives carry native addresses; pasted colons, constants and inlined primitives
  have address 0. The source map is emptied.

## Not supported yet

`build_native()` raises `NotImplementedError` rather than miscompiling:

- colon definitions inside `in-bank` (banked data is supported);
- `'` used outside the `' name ,` idiom, for example `' word constant xt`;
- `:::` words that use IX;
- `--fsym` / `zt inspect`, which describe threaded cells;
- SLD trace lines (labels are written, per-cell traces are not).

## Next steps the IR now allows

1. Peephole on IR rather than tokens: `var @` → `LD HL,(nn)`, literal operands
   (`5 +` → `LD DE,5 / ADD HL,DE`), constant folding.
2. Compare-and-branch fusion so `< if` tests flags instead of building a boolean.
3. A compact mode for cold words (shared entry/exit helpers) to trade speed for bytes.
4. Make native the default, then delete the threaded paths: NEXT/DOCOL/EXIT, `inline_next`,
   `native_control_flow`, the inline whitelist, `ZT_VERIFY_IR`, the tree shaker.
