# zt — Milestone history

This document records the milestones the compiler has shipped, in roughly
the order they landed, with pointers to the code and tests that anchor each
one. Forward-looking work (everything not yet shipped) lives in
[`COMPILER-ROADMAP.md`](COMPILER-ROADMAP.md) and
[`FORTH-ROADMAP.md`](FORTH-ROADMAP.md); the 128K sub-project has its own
detailed history in [`128k-architecture.md`](128k-architecture.md).

The "M-numbers" are referenced from other docs (e.g. *"the tag machinery
sketched in `PLAN.md` M4"*); their meaning is defined here.

---

## M0 — Bootstrap ✅

The minimum viable cross-compiler: tokenize a `.fs` file, recognise `:`/`;`
colon definitions, emit indirect-threaded code, write a Spectrum 48K `.sna`
that runs in an emulator.

**Landed:** `compile/tokenizer.py`, `compile/compiler.py`, `assemble/asm.py`,
`format/sna.py`, the `NEXT`/`DOCOL`/`EXIT` triad in `assemble/primitives.py`.

## M1 — Core primitive set ✅

Stack manipulation, basic arithmetic, comparison, logic, and 16-bit memory
access. Enough to write loops by hand using `BRANCH`/`0BRANCH` and to compute
real values.

**Forth-visible:** `dup drop swap over rot nip tuck 2dup 2drop 2swap >r r> r@
+ - 1+ 1- 2* 2/ negate abs min max and or xor invert lshift rshift
= <> < > 0= 0< u< @ ! c@ c! +!`.

## M1.25 — Multiplication and unsigned division ✅

`*` and `u/mod` as primitives. Signed `/`, `/mod`, `mod` are then defined in
[`stdlib/core.fs`](../src/zt/stdlib/core.fs) on top of `u/mod`.

**Landed:** `create_multiply`, `create_u_mod_div` in
`assemble/primitives.py`. Tests: `test_primitives.py` covers both.

## M1.5 — Bulk memory and Spectrum I/O ✅

`cmove`, `fill`, `border`. The `cmove`/`fill` pair makes screen blits and
attribute paints expressible in Forth without a Z80 escape hatch. `border`
exposes port `$FE` writes.

## M2 — Variables, constants, allotment ✅

`variable`, `constant`, `create`, `,` (comma), `c,`, `allot`. Word data
addresses become first-class via `Word.data_address`, which is what the
test runner reads to extract assertion expected/actual values.

## M3 — Compile-time control flow ✅

`if`/`else`/`then`, `begin`/`again`/`until`, `while`/`repeat`. Built on
top of the `BRANCH` and `0BRANCH` runtime primitives plus the
`ControlStack` (`compile/control_stack.py`). Tagged-control-stack errors
are still on the roadmap (see `COMPILER-ROADMAP.md` §2.4).

## M4 — Counted loops and runtime control-flow primitives ✅

`do`/`loop`/`+loop`, `i`, `j`, `leave`, `unloop`. Required new runtime
primitives: `(do)`, `(loop)`, `(+loop)`, `i`, `j`, `unloop`, plus
`0branch` (already used by `if`/`while`/`until`). The native control-flow
emission path that landed alongside M4 is documented in
[`NOTES-native-control-flow.md`](NOTES-native-control-flow.md).

**Tests:** `test_controlflow.py`.

## M5 — Text I/O and strings ✅

`emit`, `key`, `key?`, `key-state`, `type`, `at-xy`, `reset-cursor`,
`scroll-attr`. Compile-time string literals: `."` and `s"`. The
`stdlib/screen.fs` and `stdlib/input.fs` modules sit on top of these.

**Tests:** `test_m5_cls.py`, `test_m5_hello.py`, `test_m5_key_integration.py`,
`test_m5_stdlib.py`, `test_m5_step2.py`, `test_m5_strings.py`,
`test_m5_type_key.py`.

## M7 — Debug surface ✅

Symbol-map output for emulators (Fuse and ZEsarUX formats), SLD output for
source-level debugging, `.fsym` JSON dump of the host-side dictionary, and
the `zt inspect` decompiler that walks the threaded code by address.

**Landed:**
- `format/mapfile.py`, `format/sld.py`, `inspect/fsym.py`
- `inspect/decompile.py` plus the `zt inspect` subcommand
- CLI flags `--map`, `--map-format {fuse,zesarux}`, `--sld`, `--fsym`

**Tests:** `test_m7_mapfile.py`, `test_m7_sld.py`, `test_m7_fsym.py`,
`test_m7_inspect.py`, `test_m7_cli.py`, `test_m7_step1.py`,
`test_m7_warnings.py`. See also `test_fsym_v2.py`.

## M9 — 128K banking ✅

Originally tracked here; the work grew large enough that it has its own
sub-milestone series (M1–M5 internal to that effort) and its own
architecture doc.

**Shipped:** `--target 128k`, `--paged-bank`, `bank@`, `bank!`,
`raw-bank!`, `128k?`, `in-bank`/`end-bank` declarations,
`build_sna_128`, `load_sna_128`, simulator banking, `.z80` v3 writer
(added after the original M5 of the 128K series). Working examples:
`examples/plasma-128k`, `examples/bank-rotator`, `examples/bank-table`,
`examples/shadow-flip`.

**See:** [`128k-architecture.md`](128k-architecture.md) for the full
hand-off note.

---

## Pending

### M8 — `.tap` output

Not yet shipped. `zt build foo.fs -o foo.tap` would produce a two-block
`.tap` (header + data) with a tiny BASIC loader stub, unblocking real
hardware. See [`COMPILER-ROADMAP.md`](COMPILER-ROADMAP.md) §1.3 for the
deliverable.

Output formats currently supported: `sna`, `z80`, `bin`.

### Beyond M9

Forward-looking work — peephole expansion, AY sound, debugger, language
server, packaging, CI, fuzz testing, alternate threading models, multi-target,
inline assembly — is in [`COMPILER-ROADMAP.md`](COMPILER-ROADMAP.md). New
primitives proposed for game development are in
[`FORTH-ROADMAP.md`](FORTH-ROADMAP.md).
