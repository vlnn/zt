# zt — optional 128K support: architectural summary

Status: **M1 complete, M2 complete, M3 complete, M4a complete, M4b
complete, M5 complete, `.z80` v3 writer complete.** All originally-scoped
milestones landed plus an additional `.z80` v3 output format needed
because the `.sna` 128K format is ambiguous to emulators. Cross-bank
*code* calls (originally a non-goal, mentioned only as a future
follow-up) remain out of scope. This doc is the hand-off note for
whoever picks it up next, whether that's a future session or another
human. It assumes familiarity with the current zt codebase.

---

## Goal

Add an opt-in `--target 128k` build path that produces a 131,103-byte
(or 147,487-byte) `.sna` playable on a ZX Spectrum 128 (Fuse/ZEsarUX
set to 128K mode), exposing the extra four 16 KB RAM banks at
`$C000–$FFFF` to Forth code. 48K output stays the default and
bit-for-bit unchanged.

---

## Background: ZX Spectrum 128 memory

The Z80 still sees only 64 KB at a time, split into four 16 KB slots:

| Slot | Address range | Contents |
|------|---------------|----------|
| 0 | `$0000–$3FFF` | One of two 16 KB ROMs (bit 4 of `$7FFD`: 0 = 128K editor, 1 = 48K BASIC) |
| 1 | `$4000–$7FFF` | Always RAM bank 5 (normal screen at `$4000–$5AFF`) |
| 2 | `$8000–$BFFF` | Always RAM bank 2 |
| 3 | `$C000–$FFFF` | Any of RAM banks 0–7, selected by bits 0–2 of `$7FFD` |

Port `$7FFD` bits:

- 0–2: which RAM bank (0–7) is paged into slot 3
- 3: screen select — 0 = bank 5 (normal), 1 = bank 7 (shadow); does *not* remap `$4000`
- 4: ROM select
- 5: lock — once set, further writes to `$7FFD` are ignored until reset
- 6–7: unused

Port is write-only (reads return floating bus). Partial-decoded: the
real match is `01xx xxxx xx1x xx0x`, so the canonical write is
`LD BC,$7FFD ; OUT (C),A`. Banks 5 and 2 alias: when bank 5 is paged
into slot 3, `$C000` and `$4000` point at the same physical bytes.
Banks 1/3/5/7 are contended.

Runtime detection: write-then-observe — set bank 0 at `$C000`, write a
sentinel, switch to bank 1, write a different sentinel, switch back to
bank 0, verify the first sentinel survived. On 48K both sentinels read
the same because there's no paging.

---

## Background: `.sna` 128K format

The existing 48K `.sna` is 49,179 bytes: 27-byte register header + RAM
banks 5, 2, and whichever-is-paged (starting at `$4000`). PC is **not**
in the header — it's pushed onto the Z80 stack, retrieved via `RETN`.

The 128K extension is strictly additive — a 48K-format dump followed by
an extra tail:

| Offset | Size | Content |
|--------|------|---------|
| 0 | 27 | Standard 48K SNA register header |
| 27 | 16 KB | RAM bank 5 |
| 16411 | 16 KB | RAM bank 2 |
| 32795 | 16 KB | Currently-paged bank at `$C000` |
| 49179 | 2 | **PC** (little-endian — *not* pushed on stack like the 48K form) |
| 49181 | 1 | Last value written to port `$7FFD` |
| 49182 | 1 | TR-DOS ROM paged flag (0 for zt) |
| 49183 | 7 × 16 KB | Remaining seven banks in ascending numeric order, skipping the one already at offset 32795 |

Total 131,103 bytes. That's the file-size discriminator against 48K.

Quirk: if the paged bank is 5 or 2, it's written twice (once as bank 5/2
in the first 48K image, once as the paged slot). The remaining-banks
list skips the one at offset 32795.

Crucial: the 128K form stores PC in the header, so the
`push-PC-on-stack-via-RETN` trick the 48K path uses is **not** applied
for 128K snapshots.

---

## Architectural principles

1. **48K stays default.** No user-visible change to existing flows. No
   primitive gets slower.
2. **Additive in the code, layered in the runtime.** Banking lives
   behind two primitives (`BANK!`, `BANK@`) and one detection word
   (`128K?`). Everything above is library-level Forth.
3. **Simulator parity.** 128K is testable in pytest the same way 48K
   is. Bulk of work lives here.
4. **TDD from the outside in.** Format → simulator → primitives →
   build-time → example. Each layer's tests use the one below.

---

## Milestones

### M1 — `build_sna_128` and `load_sna_128` (format work) ✅

**Status: complete. 94 tests green.**

Both sizes encoded as constants: `SNA_128K_TOTAL_SIZE = 131_103` (normal)
and `SNA_128K_DUPLICATED_SIZE = 147_487` (when `paged_bank ∈ {2, 5}`
triggers the duplication-quirk tail). `tail_bank_order(paged_bank)`
promoted to public as the single source of truth for the format's
ordering rule, shared by writer and loader. `Sna128Image` is a frozen
dataclass with `memory: bytearray` (flat 128 KB, bank N at
`[N*0x4000 : (N+1)*0x4000]`), `port_7ffd: int`, `pc: int`.
`detect_sna_kind(path)` returns `"48k" | "128k"` based on file size.

`src/zt/format/sna.py` gained a sibling to `build_sna`. Existing
`build_sna` signature unchanged.

```python
build_sna_128(
    banks: dict[int, bytes],       # bank_id -> 16KB; missing = zeroed
    entry: int,                    # PC; stored in header, not pushed
    paged_bank: int,               # which bank is at $C000 at start
    data_stack_top: int = 0xFF00,
    border: int = 7,
    port_7ffd: int | None = None,  # default: paged_bank | 0x10
) -> bytes
```

Decisions:

- Banks dict-keyed so callers write a sparse map; the writer
  zero-pads absent banks.
- `entry` goes to offset 49179 directly; no stack push. Two distinct
  code paths, same module.
- `port_7ffd` defaults to `paged_bank | 0x10` (bit 4 = 48K BASIC ROM,
  conventional game default). Exposed for the odd case wanting shadow
  screen (bit 3) or locked paging.
- Validator: `paged_bank in range(8)`, `entry >= 0x4000`, every
  supplied bank ≤ 16 KB.

Mirror in `image_loader.py`:

- `load_sna_128(path) -> (mem128: bytearray, port_7ffd: int, pc: int)`
  — flat 128 KB array indexed by `bank * 0x4000 + offset`.
- `load_sna` unchanged for 48K files.
- `detect_sna_kind(path) -> Literal["48k", "128k"]` driven off file
  size.

Tests (`tests/test_sna_128.py`):

- Total size is exactly 131,103.
- Header bytes 0–26 match 48K layout (re-parametrise the existing
  `test_sna_sp_in_header_is_dstack_minus_two`-style tests).
- PC at offsets 49179/49180 round-trips.
- `$7FFD` byte at 49181 matches `paged_bank`.
- TR-DOS byte at 49182 is 0.
- Bank 5 at offset 27, bank 2 at 16411, paged bank at 32795 —
  parametrised across a few `paged_bank` values.
- Remaining seven banks appear in ascending order at 49183, skipping
  the paged one, **with the duplication quirk** for `paged_bank in (2, 5)`.
- Round-trip `build → load` preserves every bank byte-for-byte.
- Rejects paged_bank outside 0–7, rejects oversized bank contents.

The opening test is a parametrised round-trip over `paged_bank in [0, 1, 3, 4, 6, 7]`
(excluding the quirk cases). One test forces writer, reader, size,
header, bank order, PC, port byte into existence.

### M2 — simulator: banked memory ✅

**Status: complete. 54 new tests, 3,074-test full suite all green.**

Implemented as a live-view design rather than slot-references: `self.mem`
in 128K mode remains a 64 KB bytearray representing the currently
mapped view. The paged bank's storage lives in `mem[$C000:$10000]`
while active; banks 5/2 live permanently in `mem[$4000:$8000]` and
`mem[$8000:$C000]`. Eight shadow bytearrays in `self._banks` hold the
at-rest state of non-paged banks. On `$7FFD` write, the old paged
slot's contents are saved (to `_banks[old]`, or to the fixed slot if
`old ∈ {5, 2}`), and the new bank is loaded into `mem[$C000:$10000]`.
This keeps the 48K hot path byte-identical to today — zero added
branching — and imposes only a cheap `if mode != "128k": return` check
on the OUT instructions.

Public API on `Z80`:
- `Z80(mode="48k" | "128k")` — constructor kwarg.
- `Z80.port_7ffd` — the paging latch (exposed, not prefixed).
- `Z80.mem_bank(n)` — returns a `bytearray` copy of bank n's current
  bytes. Reads from the fixed slot for 5/2, from the live `$C000`
  region for the paged bank, otherwise from `_banks[n]`.
- `Z80.load_bank(n, data)` — routes writes to the same place
  `mem_bank(n)` reads from (for test setup).
- `Z80.page_bank(n)` — programmatic paging without an `OUT`
  instruction (preserves bits 3–7 of the latch).
- All three 128K helpers raise `RuntimeError` in 48K mode.

`ForthMachine(mode="48k" | "128k")` propagates mode to the inner
`Z80`. `ForthResult.page_writes: list[int]` captures all values
written to `$7FFD`, filtered from `_outputs` parallel to
`border_writes`.

Module-level `is_7ffd_write(port: int) -> bool` implements the
partial-decode check `(port & 0x8002) == 0` — one place, used by both
OUT handlers and the `ForthResult` extractor.

ED 79 (`OUT (C),A`) added to `_exec_ed` with 12 T-states. This was
missing before and is the canonical 128K paging instruction; it now
works in both modes (128K: triggers paging; 48K: captured in
`_outputs` only).

#### Sharp edges that turned out to matter

**Bank 5/2 paged into slot 3** — the reconciliation is asymmetric:
writes to `mem[$C000]` while bank 5 is paged there propagate back to
`mem[$4000]` on page-out (via `_save_paged_slot`); writes to
`mem[$4000]` during the same period do *not* propagate to slot 3. A
pathological pattern that writes to both slots concurrently will see
the slot-3 writes win at page-out time. No real zt program does this.
Loading bank 5/2 into slot 3 uses a *copy* from the fixed slot
(`bytes(self.mem[fixed])`), not an alias — so subsequent writes are
tracked correctly from that point forward.

**`mem_bank` returns copies**, not views. Tests that need to assert on
bank contents unwrap the bytearray immediately; no test so far has
needed a live view into a non-active bank. If that becomes necessary,
a `mem_bank_view(n)` returning a `memoryview` can be added alongside.

**`load_bank` is a first-class helper**, not in the original plan. It
fell out naturally from `mem_bank` — having read access without write
access would have been awkward for test setup and for the M4 compiler
that will populate banks before emitting the `.sna`.

---

### M2 — simulator: banked memory (original plan, kept for reference)

The only structurally invasive piece. Today `Z80.mem` is a flat
`bytearray(65536)`; `_rb`/`_wb`/`_rw`/`_ww` index it directly.

Replace with a `BankedMemory` object owning:

- `rom: bytearray(0x8000)` — two 16 KB ROMs, zeroed unless explicitly
  loaded (tests don't need ROM; zt never runs ROM code).
- `banks: list[bytearray]` of eight 16 KB RAM banks.
- `port_7ffd: int` — the latch, with bit-5 lock honoured.
- A cached 4-tuple slot map, rebuilt only when `$7FFD` is written.

Two modes, set at construction:

- `mode="48k"` (default) — falls through to a single flat 64 KB
  `bytearray`, behaves exactly as today. Writes to `$7FFD` ignored.
  No `if self._mode` in the 48K hot path.
- `mode="128k"` — full banked path; hot-path access is
  `self._slots[addr >> 14][addr & 0x3FFF]`.

`Z80._rb`/`_wb`/`_rw`/`_ww` become one-line delegates.

Sketch:

```python
class BankedMemory:
    def __init__(self, mode: str = "48k") -> None:
        self._mode = mode
        if mode == "48k":
            self._flat = bytearray(0x10000)
        else:
            self._banks = [bytearray(0x4000) for _ in range(8)]
            self._rom = bytearray(0x8000)
            self._port_7ffd = 0

    def read(self, addr: int) -> int: ...
    def write(self, addr: int, value: int) -> None: ...
    def write_port_7ffd(self, value: int) -> None: ...
    def bank(self, n: int) -> bytearray: ...
    def flat_view(self) -> bytearray: ...
```

`m.mem` becomes a property. In 48K mode it returns the real array. In
128K mode it returns a synthesised `bytearray` rebuilt on access —
slow, but only tests use this path; production simulator code goes
through `read`/`write`. Audit existing `m.mem[...]` pokes and move
them to `m.load()` where sensible.

Port dispatch — both `_op_out_n_a` and the new `_op_out_c_r`
(ED 41/49/51/59/61/69/79) route through:

```python
def _is_7ffd_write(port: int) -> bool:
    return (port & 0x8002) == 0
```

A15=0, A1=0 matches `$7FFD`, `$7FFF`, `$FFFD`... one function, two
call sites.

**ED 79 (`OUT (C),A`) is not currently implemented.** Canonical 128K
code uses it for `$7FFD` writes. Adding it is a one-line entry in
`_exec_ed`; flag so it's not forgotten on the critical path.

Public facing:

- `ForthMachine(mode="48k")` exposes `mode`.
- `ForthResult` grows `page_writes: list[int]` — parallel to
  `border_writes` — capturing every `$7FFD` write during a run.
- `m.mem_bank(n) -> bytearray` and `m.page_bank(n)` for tests that
  need to poke a bank that isn't currently mapped.

Tests (`tests/test_sim_128k.py`):

- Writes to `$C000` only affect the currently paged bank; paging
  another bank in and reading `$C000` shows different bytes.
- `$4000–$7FFF` is always bank 5 regardless of paging.
- Bit-5 lock: once set, further `$7FFD` writes ignored.
- `ForthResult.page_writes` records the full sequence.
- 48K mode byte-identical to current behaviour — re-run a subset of
  `test_sim.py` parametrised across both modes as a regression guard.

### M3 — primitives: `BANK!`, `BANK@`, `128K?` ✅

**Status: complete. 47 new tests, 3,123-test full suite all green.**

Landed as four `create_*` functions in `src/zt/assemble/primitives.py`:
`BANK!` (masks low 3 bits, preserves upper), `BANK@` (reads shadow),
`RAW-BANK!` (no mask, for lock-bit and ROM-select use), `128K?`
(write-A5 / page / write-5A / page-back / read / compare; returns
`0xFFFF` for TRUE, `0x0000` for FALSE). Constants exported from the
same module: `BANKM_ADDR = 0x5B5C`, `PORT_7FFD = 0x7FFD`,
`PAGE_MASK = 0x07`, `UPPER_MASK = 0xF8`.

One opcode added to `src/zt/assemble/opcodes.py`:
`_no("out_c_a", 0xED, 0x79)`. The simulator side was already in place
from M2.

The plan's `DI / ... / EI` bracketing around the port write was
dropped — zt runs with interrupts disabled by default, and emitting
`EI` would incorrectly turn them on after each `BANK!`.

#### The stack-placement discovery

zt's default data stack lives at `$FF00` and return stack at `$FE00`,
both **inside the paged slot 3**. Calling `BANK!` from code using
those defaults swaps the stacks out with the bank itself. Fix:
`ForthMachine(mode="128k")` now defaults to
`DEFAULT_DATA_STACK_TOP_128K = 0xBF00` and
`DEFAULT_RETURN_STACK_TOP_128K = 0xBE00`, placing both stacks in bank 2
(the permanently-mapped `$8000–$BFFF` slot). The `__init__` signature
changed `data_stack_top` and `return_stack_top` to `int | None`;
`None` triggers mode-based defaulting via `_default_data_stack_top` /
`_default_return_stack_top` helpers.

**Direct implication for M4.** The CLI's `--target 128k` path must
use the same 128K stack defaults, and should *reject* combinations
like `--target 128k --dstack 0xFF00` as a configuration error. In
128K mode, both stacks must live outside the paged slot — this is
non-negotiable, not a style preference.

#### `128K?` is destructive

The probe writes sentinels to `$C000` in banks 0 and 1, and the
restoration only pages back to the user's previous bank — it can't
undo the sentinel writes. Call `128K?` once at startup, before
loading bank 0 or bank 1 with real data. Documented in the primitive's
docstring.

---

### M3 — primitives: `BANK!`, `BANK@`, `128K?` (original plan, kept for reference)

In `src/zt/assemble/primitives.py`:

- `BANK! ( n -- )` — masks n (0–7) into the shadow's low bits,
  preserving screen/ROM/lock bits, then `DI ; LD BC,$7FFD ; OUT (C),A ; EI`.
- `BANK@ ( -- n )` — returns low 3 bits of the shadow. No port read.
- `128K?` ( `-- flag` ) — runtime detection via the write-then-observe
  idiom above.
- `RAW-BANK! ( n -- )` — escape hatch; writes full byte, no masking.

Shadow location: **`$5B5C`**. That's the canonical `BANKM` address the
real 128K ROM uses. In bank 5 (always mapped), in the SYSVARS region,
below any reasonable stack top. Using it means 128K programs look
idiomatic and can interoperate with external code that reads the
standard shadow.

Static-assert in the 128K compiler path: if any allocated code or data
would land on `$5B5C`, error out with a clear message. One byte of
zt-reserved RAM at a fixed address.

Tests (`tests/test_primitives_128k.py` plus a `.fs` test file):

- `BANK!` with 0..7 writes correct port value — inspect
  `ForthResult.page_writes`.
- Round-trip: write to `$C000`, `BANK! n`, write again, `BANK! m`,
  read, `BANK! n`, read — each bank retains its own value.
- `BANK@` returns what `BANK!` last wrote.
- `128K?` returns true in 128K simulator mode, false in 48K.
- Bit-5 (lock) and bit-4 (ROM) survive a `BANK!` call.

### M4a — build-time 128K target (CLI side) ✅

**Status: complete. 23 new tests, 3,146-test full suite all green.**

CLI gained `--target {48k,128k}` (default `48k`) and `--paged-bank N`
(0..7, valid only with `--target 128k`). `--dstack` and `--rstack`
changed to default `None`, resolved per mode by `_resolve_stack_defaults`:
48k picks `$FF00`/`$FE00`, 128k picks `$BF00`/`$BE00`. Validation
rejects stacks or origin in the paged slot `$C000+` under `--target 128k`,
rejects out-of-range paged_bank, and rejects `--paged-bank` without
`--target 128k`.

`_image_to_banks(image, origin)` maps the compiled image to bank 2
($8000–$BFFF) or bank 5 ($4000–$7FFF) depending on origin. `_write_output`
routes to `build_sna_128(banks, entry, paged_bank, data_stack_top, border)`
when `--target 128k`, otherwise falls through to the existing 48k path
byte-identically.

**What this unlocks today.** A 128K Forth program can now be built
end-to-end: code goes into bank 2, M3 banking primitives (`BANK!`,
`BANK@`, `128K?`, `RAW-BANK!`) can directly populate other banks at
runtime via `$C000`-region writes, and the output loads in Fuse or
ZEsarUX set to 128K mode. Code is limited to one 16 KB bank for this
milestone (bank 2 by default).

#### Caveats to document

- Code must fit in a single 16 KB bank. Attempting to compile a larger
  program under `--target 128k` will fail with a clear error pointing
  at M4b. The 48K toolchain retains its full `$8000-$FFFF` code range.
- Data tables that won't fit alongside code in the code bank must be
  initialised at runtime by paging the target bank in and writing via
  `BANK!` followed by direct pokes. Declarative `CREATE`-in-bank is
  M4b work.

---

### M4b — compiler-side bank declarations ✅

**Status: complete. 14 new tests, full suite green.**

The surface turned out smaller than the original plan sketched. Two
new directives — `in-bank ( n -- )` and `end-bank` — and two new
public `Compiler` methods — `bank_image(n) -> bytes` and
`banks() -> dict[int, bytes]`. No new word kind; CREATE inside a
banked region stays a `variable` kind with the data_address pointing
into the `$C000–$FFFF` range.

The refactor stayed mechanical thanks to the emitter's pre-existing
`begin_buffered` / `commit_buffered` pattern — swapping `self.asm`
between Asm instances was already the compiler's idiom. Added to
`Compiler.__init__`: `self._main_asm`, `self._bank_asms: dict[int, Asm]`
(each at origin `$C000`), `self._active_bank: int | None`.
`_activate_bank(n)` lazily creates bank N's Asm if needed and swaps
`emitter.asm`; `_deactivate_bank()` swaps back to `_main_asm`.

The one non-obvious change was `_emit_variable_shim`: its existing
behaviour emitted code+data contiguously into `self.asm`. For banked
CREATE, the code shim must still live in main-bank (because NEXT
threading targets absolute addresses assuming the code is always
visible), while data bytes go wherever `self.asm` points — which is
now the bank's Asm. So `_emit_variable_shim` writes code through
`self._main_asm` directly and reads `data_addr` from `self.asm.here`
(the active target). That's the only place in the compiler that
needs to distinguish between "code" and "data" emission targets.

`_variable` still emits its zero-cell through `self.asm` (not
`_main_asm`), so `variable foo` inside a `N in-bank ... end-bank`
region gets its cell in bank N. This was free — the shim split
covered it.

CLI integration: `_write_output` in `src/zt/cli/main.py` changed one
line — `banks.update(compiler.banks())` after `_image_to_banks` — so
that the per-bank buffers land in the dict passed to `build_sna_128`.
The main image still occupies bank 2 via the existing
`_image_to_banks` logic; the new call merges in any `in-bank`
contents alongside.

#### Sharp edge: `128K?` is destructive to compile-time data

The detection probe writes `$A5` and `$5A` sentinels to `$C000` in
banks 0 and 1. If a program uses `in-bank 0` or `in-bank 1` to place
compile-time data, calling `128K?` *after* paging those banks in
would read the sentinels instead of the data; calling it at startup
is fine, but the data-at-offset-0 pattern is common enough to be a
trap. Three ways around it:

- Only place compile-time data in banks 3/4/6/7 (avoid the probe's
  scratch banks entirely).
- Start compile-time data at offset ≥ 2 within the bank, leaving a
  scratch word at the start.
- Drop `128K?` and build 128K-only — the `.sna` is already 131 KB;
  loading it on a 48K emulator fails at the file level, not at
  runtime. Documented in the bank-table demo's header comment.

---

### M4b — compiler-side bank declarations (original plan, kept for reference)

Pulled out of the original M4 plan as its own milestone because the
scope turned out to be larger than "plumbing": per-bank `here`
pointers require multiple `Asm` instances routed by a "current bank"
state, `CREATE`/`,`/`C,` need to emit into the active bank's buffer,
and cross-bank address references need to emit `BANK!` shims or
resolve to a trampoline. None of it starts until after M4a.

In `src/zt/compile/compiler.py`:
- A new `BANK` word `( u "name" -- )` that reserves a bank id for a named region,
  e.g. `0 BANK level-data` declares bank 0 as holding `level-data`.
- Bank contents come from `CREATE`/`,`/`C,` emitted while a `BANK` is active.
  The compiler tracks a per-bank `here` pointer alongside the normal one.
- Cross-bank data addressing shim: emits `BANK! ... load/store ... BANK!` around
  each access, with the original bank restored from the shadow.
- The build output path collects every bank's bytes and passes them as the
  `banks` dict to `build_sna_128`.

Still deferred beyond M4b: cross-bank code calls (needs a trampoline
in a bank that's always mapped — bank 2 is natural).

---

### M4 — build-time 128K target (original plan, kept for reference)

CLI:

- `zt build foo.fs -o foo.sna --target 128k` → 131,103-byte `.sna`.
- Default stays `48k`. `--target` is the only knob. No environment
  variable, no config file.
- `--code-bank N` (default 0) — which 16 KB bank holds code that sits
  in slot 3. M4 keeps the simple layout: main code at `$8000` in bank 2.

Compiler changes (`src/zt/compile/compiler.py`):

- New word `BANK ( u "name" -- )` declaring a named bank region, e.g.
  `0 BANK level-data`. Per-bank `here` pointer alongside the normal one.
- `CREATE`/`,`/`C,` emitted inside a `BANK` block populate that bank's
  buffer.
- The compiler emits an addressing shim for cross-bank *data* access:
  save current bank, `BANK!` target, access, restore.
- Output via `build_sna_128(banks=..., entry=..., paged_bank=...)`.

**M4 covers cross-bank data only, not cross-bank code calls.** See
non-goals.

Stdlib (`src/zt/stdlib/banking.fs`):

- `: bank-call ( bank-id xt -- ... )` — save-switch-exec-restore wrapper.
- `: ensure-128k 128K? 0= if ." needs 128k" cr bye then ;`
- Convenience words `bank0 .. bank7` pushing their numeric id.

Tests (`tests/test_cli_128k.py`, `tests/test_compiler_banking.py`):

- `zt build --target 128k` produces a 131,103-byte file.
- Example program fills bank 0 with `0x55`, bank 1 with `0xAA`,
  switches between them, reads both back, renders the result — run
  end-to-end through the 128K simulator.
- Default (no flag) produces byte-identical 48K output for the plasma
  example. **This is the regression guard**; it catches drift from the
  `Z80.mem → BankedMemory` refactor.

### M5 — acceptance demos ✅

**Status: complete. Three examples ship; 40 new tests green.**

The plan called for `examples/plasma-128k/`. That got built, alongside
two smaller demos that cover the other banking workflows users will
want. All three demonstrate different things:

**`examples/plasma-128k/main.fs`** — the headline demo. Double-buffered
plasma using the ZX 128 shadow screen. Bank 5 ($4000) and bank 7
(accessible at $C000 when paged) each hold a full Spectrum screen
(6144-byte bitmap + 768-byte attrs). The runtime loop draws plasma
into whichever screen is currently hidden, then toggles bit 3 of
`$7FFD` via `RAW-BANK!` — one port write swaps which bank the ULA
renders from. Zero copying, atomic frame presentation, genuinely
impossible on a 48K Spectrum. 19 tests in
`tests/test_examples_plasma_128k.py`; two of them actually run the
simulator through enough plasma frames (~25 s wall clock) to verify
both screens receive data and bit 3 toggles between draws.

**`examples/bank-rotator/main.fs`** — runtime bank seeding via
`BANK!`+`C!`. Demonstrates `128k?` detection at startup (halts with a
red border on a 48K machine as a visible failure signal), `BANK!` to
seed six banks with distinctive attribute bytes, then a `cycle` loop
that pages each bank in and paints its byte to the corresponding
column of the screen attribute row. 14 tests in
`tests/test_examples_bank_rotator.py`.

**`examples/bank-table/main.fs`** — compile-time bank population via
M4b's `in-bank` CREATE. Same visible effect as bank-rotator, but the
colour bytes live in banks 0/1/3/4 at compile time instead of being
seeded at runtime. 7 tests in `tests/test_examples_bank_table.py`.
Demonstrates why the two workflows aren't interchangeable: this demo
can't use `ensure-128k` because the `128K?` probe would overwrite the
compile-time data in banks 0 and 1 before `main` reads it.

#### Shadow-screen support in the simulator

Implementing plasma-128k required a small, additive change in
`src/zt/sim.py` — the original architectural doc had shadow screen
flagged as "non-goal, needs `decode_screen_*` changes", which turned
out to be pessimistic. For a demo that just draws and observes, the
existing `mem_bank(n)` infrastructure was enough; all that was missing
was observational sugar:

- `PORT_7FFD_SCREEN_BIT = 0x08` — bit 3 of the paging latch
- `NORMAL_SCREEN_BANK = 5`, `SHADOW_SCREEN_BANK = 7`
- `SCREEN_BITMAP_SIZE = 6144`, `SCREEN_ATTRS_SIZE = 768`
- `Z80.displayed_screen_bank() -> int` returns 5 or 7 based on bit 3
- `Z80.displayed_screen() -> tuple[bytes, bytes]` returns the
  ULA-visible bank's bitmap and attrs

Both methods are `_require_128k`-guarded. The existing
`decode_screen_*` text-screen introspection helpers still read from
`$4000` directly — they're only used by zt's own test infrastructure
which always writes to the normal screen, so adapting them wasn't
needed. If shadow-screen text introspection becomes useful later,
that's a ~10-line diff to parameterise them by base address.

End-to-end CLI verification: all three demos build cleanly via
`zt build <demo>/main.fs -o out.sna --target 128k`, producing
131,103-byte snapshots that load in Fuse/ZEsarUX set to 128K mode.

---

### `.z80` v3 writer ✅ (added after M5)

**Status: complete. 39 new writer tests + 5 CLI tests; 3,220-test full suite green.**

#### Why this existed in the first place

After M5 landed, the plasma-128k `.sna` was rejected by Fuse with
"SNA could not be opened". Investigation via `snapdump` (libspectrum's
inspection tool) revealed the actual problem:

```
machine: Pentagon 128K
```

The `.sna` 128K format has **no machine-type field**. Bytes 49179–49182
hold PC, `$7FFD`, and the TR-DOS flag; no byte identifies whether the
snapshot was taken on a Spectrum 128, +2, +2A, or Pentagon 128.
libspectrum's heuristic defaults all 128K SNAs to Pentagon 128. Fuse
launched with `--machine 128` then refuses to load a Pentagon
snapshot without GUI intervention. The file was technically spec-correct
and byte-for-byte matched the zxnet.co.uk specification; it just
couldn't be loaded as a Spectrum 128 snapshot.

The fix was to add an alternate output format that has an explicit
machine-type byte. `.z80` v3 fits: offset 34 in the extended header is
the "hardware mode" byte, and value 4 explicitly means Spectrum 128.
`snapdump` on a `.z80` v3 output now reports `machine: Spectrum 128K`
unambiguously.

#### What landed

`src/zt/format/z80.py` — a new `build_z80_v3(banks, entry, paged_bank,
data_stack_top=0xBF00, border=7, port_7ffd=None) -> bytes` writer.
Layout:

- 30-byte base header with base-header PC=0 (signals v2/v3 extended
  format), A/F = 0, BC/DE/HL/IX/IY = 0, SP at offset 8, border and
  compression flags at offset 12.
- Length word at offset 30 = 54 (signals v3 extended header).
- 54-byte extended header: PC at offset 32, hardware mode at offset 34
  (= 4 for Spectrum 128), last `$7FFD` write at offset 35, sound-chip
  registers zeroed.
- 8 memory blocks, one per RAM bank, each framed as
  `length:2 page:1 data:16384`. Length word `0xFFFF` signals an
  uncompressed 16 KB block per the v3 spec. Pages 3–10 correspond to
  RAM banks 0–7.
- Total size: 86 + 8×(3+16384) = 131,182 bytes.

CLI integration: `--format z80` accepted alongside `--format sna`,
routes to `build_z80_v3`. `.z80` extension auto-detected. `--format z80
--target 48k` rejected with a clear error. The `compiler.banks()`
dict is merged into the code image the same way as the `.sna` path.

Tests: `tests/test_z80_format.py` — 39 writer tests (header layout,
extended-header fields, memory-block framing, uncompressed marker,
bank-to-page mapping, size, round-trip). `tests/test_cli_128k.py` —
5 new CLI tests covering extension-routing, explicit format flag,
48k rejection, hardware-mode byte, and PC placement.

#### Why keep `.sna` 128K at all then?

A few emulators (older or embedded) accept only `.sna`. The `.sna`
writer is spec-correct; it just loses if the user doesn't explicitly
tell the emulator the machine type. The Makefile now produces both
`.sna` and `.z80` for each 128K example, and the default CLI behaviour
is to honour whichever extension the user names. Users who hit
machine-type confusion have `--format z80` as the escape hatch.

#### Sharp edge noted for future z80 work

The v3 writer here is strictly the minimum needed for a loadable
128K snapshot: uncompressed blocks, no AY register state, no T-state
counter, no joystick mapping. Programs using the AY chip or needing
cycle-exact resume will need v3 extensions. That's future work; nothing
in the current feature set exercises those fields.

---

### M5 — example: `examples/plasma-128k/` (original plan, kept for reference)

Variant of `examples/plasma/` that stores a precomputed phase buffer
in bank 3 and a second palette table in bank 4. Demonstrates >48 KB
reachable from a single program. `make examples` produces
`build/plasma-128k.sna`. Loads in Fuse set to 128K mode. Doubles as
acceptance test and documentation.

Plus `docs/128k.md`: memory map, the two primitives, `--target 128k`,
the detection idiom, the screen-aliasing warning (see sharp edges).

---

## Design decisions settled

**`BANK!` preserves upper bits.** Masks `(shadow & 0xF8) | (n & 0x07)`.
Matches the idiom in the 128K tech FAQ. `RAW-BANK!` for the rare case
that needs to touch the full byte.

**Default `$7FFD` startup value: `paged_bank` alone, no extra bits.** Bit
4 = 0 selects Pentagon BASIC ROM (libspectrum always identifies 128K
SNAs as Pentagon, so this is the ROM that matters). Bit 4 = 1 would
select TR-DOS on Pentagon, which is not what zt programs want.
Originally this default was `paged_bank | 0x10` on the theory that
48K-BASIC-ROM-in-slot-0 was game-convention; that was wrong for
Pentagon. Fix verified by real-hardware testing: Fuse loaded both with
and without bit 4 set, the `bit 4 = 0` version ran correctly.

**Default `paged_bank` = 7.** The CLI's `--target 128k` without
`--paged-bank` defaults to bank 7 in slot 3, not bank 0. Real-hardware
evidence: snapshots with `paged_bank = 0` loaded as pure black on
Fuse/Pentagon, while `paged_bank = 7` loaded and displayed correctly.
The suspected reason is display-wiring state on cold-load being
established differently by the initial `$7FFD` write Fuse issues when
parsing the snapshot, but we never root-caused it — we just observed
that 7 works and 0 doesn't, and defaulted to 7.

**Shadow at `$5B5C`.** Canonical address used by the 128K ROM's
`BANKM`. One byte, bank 5, always mapped.

**128K stacks live in bank 2, non-negotiable.** Both data stack
(`$BF00` default) and return stack (`$BE00` default) must sit in the
always-mapped `$8000–$BFFF` region. The 48K defaults (`$FF00` /
`$FE00`) sit in the paged slot 3, which means `BANK!` would swap them
out with the bank data — catastrophic. Enforced by mode-aware defaults
in `ForthMachine.__init__` and (in M4) in the CLI's `--target 128k`
validation.

**Mode set at `Z80(mode=...)` construction, not dynamically.** Keeps
the 48K hot path free of branches.

**Cycle-accurate mode ignores `$C000` contention.** Current simulator
doesn't model `$4000` contention either. Explicit non-goal; document,
don't fix.

---

## Non-goals

- **Cross-bank code calls.** M4 does cross-bank data. Jumping into
  code in another bank needs a trampoline in a bank that's always
  mapped (slot 2, bank 2 is natural). Design pass of its own: where
  the trampoline lives, how it interacts with the inliner, how
  `EXIT`s know which bank to restore. Follow-up milestone.
- **+2A/+3 extended paging (port `$1FFD`).** The 128K `.sna`
  extension can't represent it. Needs a `.z80` v3 writer long-term.
- **Shadow screen (bank 7, bit 3).** Paging mechanism is free once
  M2 lands, but switching which screen the ULA renders from needs
  `decode_screen_*` changes. Defer.
- **AY-3-8912 sound.** Tier 4.2 in `COMPILER-ROADMAP.md`,
  unrelated to banking.

---

## Sharp edges

**Attribute byte ≠ what you think when pixels are zero.** Spectrum
attribute bytes are `FBPPPIII` where I=ink, P=paper, B=bright, F=flash.
If you paint attrs without also setting pixels, every cell shows solid
*paper* colour — ink is irrelevant because no pixels are lit to show
it. `$47` (bright white ink, black paper) with zero pixels = black
screen, NOT white. For "solid bright white", use `$78` (black ink,
bright white paper). For "solid bright red", `$50`. This cost us an
evening of "why isn't my shadow screen working" when the shadow screen
was working perfectly and we were just painting invisible ink on black
paper. Always test attribute constants with a single-cell example
before baking them into a demo.

**`paged_bank = 0` at SNA load time fails on Fuse/Pentagon.** Empirical:
`$7FFD = $00` snapshots load as black screen; `$7FFD = $07` load fine.
We didn't root-cause this, just observed it and defaulted `--paged-bank
7` in the CLI. If you pass an explicit `--paged-bank 0` and see nothing,
this is why. Try 7.

**`.sna` 128K machine-type ambiguity.** The format has no
hardware-type field; libspectrum defaults every 128K SNA to Pentagon
128, which means Fuse launched with `--machine 128` refuses to load it
without GUI intervention. Not a zt bug — a format limitation. Worked
around by also shipping `.z80` v3 output (hardware byte at offset 34
explicitly names Spectrum 128). **Use `.z80` as the default for
emulator loading; keep `.sna` for tools that accept only that.**

**Screen aliasing.** Bank 5 paged into slot 3 means a write to
`$C000` lands on screen row 0 at `$4000`. Physically correct,
inevitably confusing. Bank 7 at `$C000` aliases the shadow screen.
Warn in `docs/128k.md` with the memory map front and centre.

**`$5B5C` collision.** Static-assert at compile time that no
allocated region overlaps. Failure message should point at the doc.

**ED 79 missing.** Current simulator doesn't implement `OUT (C),A`.
Banking tests need it immediately. One-line fix in `_exec_ed`, but
explicitly on the M2 path.

**48K regression guard.** The `BankedMemory` refactor is the kind of
change that drifts output by one byte somewhere deep. Golden-file
assertion on the plasma 48K `.sna` on every PR that touches `sim.py`
or `sna.py`. Cheap insurance.

**Milestone-creep temptation.** M4 without cross-bank calls feels
incomplete. Resist. Cross-bank data alone is a clean, demoable slice;
cross-bank calls bundled in is how two weeks becomes six.

---

## Ordering rationale

M1 is pure byte-layout — fastest to TDD, no simulator dependency, and
prerequisite for M2's test fixtures (we need `load_sna_128` to assert
on simulator state). M2 unlocks M3 and M4 (no simulator → no primitive
tests → no compiler tests). M3 is small and mechanical once M2 lands.
M4 is the user-facing work, naturally last. M5 is the acceptance gate.

Rough sizing: M1 ~1 day, M2 ~3–5 days (`Z80` refactor touches every
memory access), M3 ~1 day, M4 ~2 days, M5 ~1 day + Fuse debugging.
Total ~2 weeks focused.

---

## Files touched summary

### Landed in M1+M2+M3+M4a+M4b+M5 + `.z80` v3 ✅

New:
- `src/zt/format/z80.py` — `build_z80_v3(banks, entry, paged_bank, ...)` writer

Modified:
- `src/zt/format/sna.py` — added `build_sna_128`, `tail_bank_order` (public), 128K size/offset constants
- `src/zt/format/image_loader.py` — added `Sna128Image` dataclass, `load_sna_128`, `detect_sna_kind`
- `src/zt/sim.py` — `mode` kwarg on `Z80` and `ForthMachine`; `is_7ffd_write` helper; `port_7ffd`, `_banks` slots; `mem_bank`, `load_bank`, `page_bank` public methods; ED 79 added to `_exec_ed`; `_maybe_handle_7ffd`/`_write_port_7ffd`/`_save_paged_slot`/`_load_paged_slot` private helpers; `page_writes` added to `ForthResult` and extracted in `_execute`; `DEFAULT_DATA_STACK_TOP_128K`/`DEFAULT_RETURN_STACK_TOP_128K` and `_default_data_stack_top`/`_default_return_stack_top` helpers; `ForthMachine.__init__` stack kwargs made mode-aware via `int | None`
- `src/zt/assemble/opcodes.py` — added `out_c_a` (ED 79)
- `src/zt/assemble/primitives.py` — added `BANKM_ADDR`, `PORT_7FFD`, `PAGE_MASK`, `UPPER_MASK` constants; four `create_*` functions (`create_bank_store`, `create_bank_fetch`, `create_raw_bank_store`, `create_128k_query`); all four registered in `PRIMITIVES`
- `src/zt/cli/main.py` — `--target {48k,128k}` and `--paged-bank` flags; `--format z80` alongside `sna`/`bin`; `_resolve_stack_defaults`, `_validate_128k_config`, `_validate_48k_config` helpers; `_image_to_banks` for 128k origin → bank routing; `_write_output` routes to `build_sna_128` or `build_z80_v3` under `--target 128k` and merges `compiler.banks()` into the banks dict
- `src/zt/compile/compiler.py` — `_main_asm`, `_bank_asms`, `_active_bank` state; `_activate_bank`/`_deactivate_bank` routing helpers; `bank_image(n)`/`banks()` public accessors; `in-bank` and `end-bank` directives; `_emit_variable_shim` split into main-bank code and active-bank data
- `Makefile` — `TARGET_128K_ROOTS` and both `TARGET_128K_SNAS`/`TARGET_128K_Z80S` target groups; `make examples` produces both formats for every 128K demo

New test files:
- `tests/test_sna_128.py` (71 tests)
- `tests/test_image_loader_128.py` (23 tests)
- `tests/test_sim_128k.py` (41 tests)
- `tests/test_forth_machine_128k.py` (13 tests)
- `tests/test_primitives_128k.py` (47 tests)
- `tests/test_cli_128k.py` (28 tests)
- `tests/test_compiler_banking.py` (14 tests)
- `tests/test_examples_bank_rotator.py` (14 tests)
- `tests/test_examples_bank_table.py` (7 tests)
- `tests/test_examples_plasma_128k.py` (18 tests)
- `tests/test_examples_shadow_flip.py` (19 tests)
- `tests/test_z80_format.py` (39 tests)

New examples:
- `examples/plasma-128k/main.fs` — double-buffered plasma via shadow screen
- `examples/bank-rotator/main.fs` — runtime bank seeding via `BANK!`+`C!`
- `examples/bank-table/main.fs` — compile-time bank population via `in-bank` CREATE
- `examples/shadow-flip/main.fs` — minimal shadow-screen flip test with pre-seeded bank 5

Simulator addition for M5 — in `src/zt/sim.py`:
- `PORT_7FFD_SCREEN_BIT`, `NORMAL_SCREEN_BANK`, `SHADOW_SCREEN_BANK`,
  `SCREEN_BITMAP_SIZE`, `SCREEN_ATTRS_SIZE` constants
- `Z80.displayed_screen_bank()`, `Z80.displayed_screen()` helpers

### Deferred beyond this plan

- **User-facing guide** (`docs/128k.md`) — complementing the
  architectural doc with a short "how to write a 128K program" that
  covers the memory map, the primitives, the CLI, the two example
  patterns, and the `128K?` sharp edge. Content is all in this doc
  and the example header comments; needs editorial sweep, not new
  material.
- **Cross-bank code calls** — a trampoline in bank 2 that saves the
  current bank, `BANK!`-switches, does a `CALL` into bank-N code,
  then restores. Flagged as a non-goal in this plan from the start;
  genuinely a larger design question (how `EXIT` knows which bank to
  restore, how the inliner handles cross-bank references).
- **+2A/+3 paging** (port `$1FFD`). Needs a `.z80` v3 writer; the
  128K `.sna` extension can't represent it.
- **Shadow screen** (bit 3 of `$7FFD`, ULA reads bank 7). Originally
  flagged as non-goal in this plan, pessimistically. The demo path
  landed in M5 via `Z80.displayed_screen_bank()` /
  `Z80.displayed_screen()` — small additive helpers on top of the
  existing `mem_bank(n)` infrastructure. The `decode_screen_*`
  text-screen introspection still reads from `$4000` directly; if
  shadow-text introspection becomes useful, that's a ~10-line change
  to parameterise by base address.
