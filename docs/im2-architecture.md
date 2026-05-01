# zt — IM 2 interrupt infrastructure: architectural summary

Status: implemented. Prerequisite for the AY-3-8912 tracker driver
(Tier 4.2 in `COMPILER-ROADMAP.md`) and any raster-synced demo work
(FORTH-ROADMAP §8.1). 137 dedicated tests across the five milestones.

---

## Goal

Add deterministic, frame-synced interrupt support to the simulator and a
Forth-level primitive `IM2-HANDLER! ( addr -- )` that installs a Z80
routine as the ULA interrupt handler. Works on `--target 48k` and
`--target 128k` with the same user-facing API. Existing 48K and 128K
outputs stay byte-identical when no IM 2 is installed.

---

## Background: Z80 IM 2

On interrupt: if `iff1` is set and the CPU isn't blocked, push PC, clear
`iff1`/`iff2`, dispatch by mode.

| Mode | Dispatch |
|------|----------|
| IM 0 | execute the byte the device puts on the bus (typically RST n) |
| IM 1 | jump to `$0038` |
| IM 2 | form vector address `(I << 8) \| bus_byte`; read 16-bit handler from there; jump |

Spectrum particulars: the bus byte during interrupt is undefined
(floating bus, commonly `$FF`). The canonical IM 2 setup defends against
this by allocating a 257-byte table all containing the same byte `V`, so
that whatever the bus byte was, the read of `(I*256+bus)` and
`(I*256+bus+1)` both yield `V`, dispatching to the address `V*0x101`.
Three bytes at that address are a `JP handler`.

Frame interrupt: 50 Hz, fired by the ULA when the beam reaches the top
of the frame. T-states per frame: 69888 (48K), 70908 (128K). `HALT`
waits for the next interrupt.

---

## Architectural principles

1. **No-op when unused.** A program that doesn't reference any IM 2
   primitive runs identically to before, byte-for-byte. The CLI uses
   liveness analysis to gate table emission.
2. **One primitive, one knob.** `IM2-HANDLER! ( addr -- )` is the
   user-facing surface for installation. Companions `IM2-HANDLER@ ( --
   addr )` and `IM2-OFF ( -- )` complete the API.
3. **Z80-level handlers only.** v1 takes a raw Z80 entry point. The
   handler is hand-written (the AY driver — the motivating case — is
   hand-written Z80 anyway). Forth-level ISRs (saving/restoring HL=TOS,
   BC=NEXT-pointer, etc.) are deferred until a second use case appears.
4. **TDD from the inside out.** ED-opcodes → interrupt firing
   mechanism → table allocator → primitives → example. Each layer's
   tests use only the one below.

---

## Structure

### Layer stack

```
            ┌──────────────────────────────────────┐
            │  user .fs source                     │
            │    ::: my-isr ... reti ;             │
            │    : main  ['] my-isr IM2-HANDLER!   │
            │            ei  begin wait-frame again│
            └──────────────────┬───────────────────┘
                               │ compile
                               ▼
        ┌──────────────────────────────────────────┐
        │  M4 — Forth primitives                   │
        │    IM2-HANDLER! / IM2-HANDLER@ / IM2-OFF │
        │    EI / DI                               │
        │    assemble/primitives.py                │
        └──────────────────┬───────────────────────┘
                           │ liveness signal
                           ▼
        ┌──────────────────────────────────────────┐
        │  M3 — Build-time table allocator         │
        │    inject_im2_table_into_ram48k()        │
        │    inject_im2_table_into_bank()          │
        │    build_sna{,_128}(im2_table=...)       │
        │    CLI: _image_uses_im2(compiler)        │
        └──────────────────┬───────────────────────┘
                           │ produces .sna
                           ▼
        ┌──────────────────────────────────────────┐
        │  M2 — Runtime firing (sim)               │
        │    fire_interrupt()                      │
        │    run_until() + frame-rate auto-fire    │
        │    bus_byte, _next_int_at, _ei_pending   │
        │    interrupt_count → ForthResult         │
        └──────────────────┬───────────────────────┘
                           │ uses
                           ▼
        ┌──────────────────────────────────────────┐
        │  M1 — ED-prefix opcodes (sim)            │
        │    ED 46/56/5E   IM 0/1/2                │
        │    ED 47/57      LD I,A / LD A,I         │
        │    ED 4D/45      RETI / RETN             │
        │    iff2 mirrored on EI/DI                │
        └──────────────────────────────────────────┘
```

Solid arrows are compile-time / build-time dependencies. At runtime the
flow inverts: the ULA's frame interrupt enters at M2's `fire_interrupt`,
which reads M3's table, jumps via M4's installed JP slot to the user's
ISR, and unwinds via M1's `RETI` back into the M4 caller.

### Vector table layout in RAM

```
        $B800 ┌──────────────────────────────────┐
              │  B9 B9 B9 ... B9 B9 B9   (257×)  │  ← M3 fills this
              │  vector table                    │     when im2_table=True
        $B900 └──────────────────────────────────┘
                           ...
        $B9B9 ┌──────────────────────────────────┐
              │  C3  LO  HI                      │  ← M3 emits C3 + 00 00
        $B9BB └──────────────────────────────────┘     M4's IM2-HANDLER!
                  ▲                                    overwrites LO/HI
                  │                                    at runtime
                  └─ JP <handler>
```

### Dispatch resolution at fire time

```
   ULA frame INT  →  Z80 ack: push PC, clear iff/iff2
                  →  read floating-bus byte  B ∈ {$00..$FF}
                  →  vector_addr = (I<<8) | B = $B8nn   (any nn)
                  →  word at $B8nn = ($B9, $B9) = $B9B9
                       — guaranteed because the table is 257 bytes of
                         $B9: whichever consecutive pair the CPU reads,
                         both bytes are $B9
                  →  PC ← $B9B9
                  →  execute JP <handler>   (the slot M4 wrote)
                  →  handler runs, ends with EI; RETI
                  →  RETI pops PC, caller resumes (typically inside
                     WAIT-FRAME, which then DI/POP IY/dispatch to the
                     next threaded cell)
```

---

## Milestones

### M1 — ED-prefix completeness (sim) — done, 47 tests

Added to `_exec_ed`:

| Opcode | Mnemonic | T-states |
|--------|----------|----------|
| 0x46   | IM 0     | 8        |
| 0x56   | IM 1     | 8        |
| 0x5E   | IM 2     | 8        |
| 0x47   | LD I,A   | 9        |
| 0x57   | LD A,I   | 9        |
| 0x4D   | RETI     | 14       |
| 0x45   | RETN     | 14       |

New `Z80` fields: `i: int = 0`, `im_mode: int = 0`, `iff2: bool = False`
(separate from the existing `iff` which represents iff1). `_op_di` and
`_op_ei` now mirror onto `iff2` per the Z80 spec. `R` register skipped
(no zt code uses it; documented as not modeled).

LD A,I sets S/Z from the loaded value, P/V from `iff2`, clears H/N,
preserves C. RETN copies `iff2` → `iff1`. RETI does not (caller must
`EI; RETI` explicitly).

Tests in `tests/test_sim_im_opcodes.py` cover each opcode, T-state cost,
flag effects, and EI/DI's effect on iff2. All parametrised across
opcodes/values per house style.

### M2 — interrupt firing mechanism (sim) — done, 36 tests

Three additions to `Z80`:

```python
bus_byte: int = 0xFF
t_states_per_frame: int        # 69888 (48k) or 70908 (128k)
_next_int_at: int              # absolute T-state deadline
```

Plus `interrupt_count: int = 0` and `_ei_pending: bool = False`. The
EI-pending flag defers the next auto-fire by exactly one instruction
after EI, matching real Z80 behavior.

New method `fire_interrupt()`: if `iff` clear → no-op. Else: clear
halted, `_halt_waiting`; push PC; clear iff1 and iff2; dispatch by
`im_mode` (IM 1 → PC=`$0038`, +13 T-states; IM 2 → PC=read-word at
`(i << 8) | bus_byte`, +19 T-states); increment `interrupt_count`.

New method `run_until(t_state_target)`: drives execution with auto-fire
at frame-rate boundaries. Pre-detects HALT-with-iff=True so the CPU
ticks `_halt_wait` (4 T-states per "NOP slot") rather than entering
the `halted=True` state, which would short-circuit the loop.

`ForthResult` gains `interrupt_count: int = 0`, propagated from
`m.interrupt_count` at result construction.

Tests in `tests/test_sim_interrupts.py` plus
`tests/test_forth_result_interrupts.py` cover: defaults, iff gate, IM 1
dispatch, IM 2 dispatch parametrised across `bus_byte` values to prove
the 257-byte property, HALT unhalt with post-HALT pushed PC, frame-rate
cadence parametrised across frames, 128K frame budget, DI prevention,
EI-pending NOP-before-fire quirk.

### M3 — vector table allocator (build-time) — done, 26 tests

`src/zt/assemble/im2_table.py` exposes:

```python
IM2_TABLE_PAGE = 0xB8
IM2_VECTOR_BYTE = 0xB9
IM2_TABLE_LEN = 257
IM2_TABLE_ADDR = 0xB800
IM2_HANDLER_SLOT_ADDR = 0xB9B9

inject_im2_table_into_ram48k(ram: bytes) -> bytes
inject_im2_table_into_bank(bank: bytes, bank_origin: int) -> bytes
```

Both helpers are pure — input not mutated. The JP slot is filled with
`JP $0000` as a fail-loud placeholder; the IM2-HANDLER! primitive
overwrites the operand at runtime.

Default placement chosen so that:
- on 128K, `$B800` lives in slot 2 (always-mapped bank 2);
- on 48K, `$B800–$B9BB` is high RAM well above screen/sysvars and well
  below default DSP at `$FF00`;
- no collision with `$5B5C` (BANKM shadow on 128K).

`build_sna(... im2_table=False)` and
`build_sna_128(... im2_table=False)` accept a keyword-only flag, default
off so existing 48K golden-file regression tests stay byte-identical.

CLI integration: `_image_uses_im2(compiler)` calls
`compiler.compute_liveness()` and checks for any of `im2-handler!`,
`im2-handler@`, `im2-off` in the live set. The flag flows automatically
to both `build_sna` and `build_sna_128` based on whether the program
actually uses the primitives.

Tests in `tests/test_im2_table.py` cover constants, helper purity, error
paths (rejecting non-containing bank origins, wrong bank size), build
integration, and the CLI auto-flag — including a regression test that
sources without IM 2 leave the table page zero.

### M4 — control primitives — done, 25 tests

Three primitives in `src/zt/assemble/primitives.py`, registered in
`CORE_PRIMITIVES`:

**`IM2-HANDLER! ( addr -- )`** — 14 bytes. DI; LD ($B9BA),HL; LD A,$B8;
LD I,A; IM 2; POP HL; dispatch. Does NOT EI — caller controls when
interrupts re-enable, so multi-step setups can install several pieces of
state atomically.

**`IM2-HANDLER@ ( -- addr )`** — 7 bytes. PUSH HL; LD HL,($B9BA);
dispatch.

**`IM2-OFF ( -- )`** — 6 bytes. DI; IM 1; dispatch. Reverts to IM 1 so a
stray fire (e.g. during shutdown) goes to ROM `$0038` rather than via
the now-stale vector table. Does not touch the I register.

Companion primitives `EI` and `DI` were also added (Forth-level
wrappers for the bare opcodes), since `IM2-HANDLER!` deliberately
doesn't EI and the user needs to from a Forth colon body.

New assembler mnemonics added to `opcodes.py` to support these
primitives and any user-written ISR: `im_0/1/2`, `ld_i_a`, `ld_a_i`,
`reti`, `retn`.

Tests in `tests/test_primitives_im2.py` cover byte-level encoding for
all three primitives, single-call execution effects on `i`, `im_mode`,
`iff`, the JP-slot operand, the round-trip `IM2-HANDLER!` →
`IM2-HANDLER@`, and a full end-to-end test where the ISR increments
`$5800` and 3 frames produce 3 increments and 3 RETIs back into the
caller.

### M5 — example + acceptance — done, 3 tests

`examples/im2-rainbow.fs`. Eighteen lines of Forth including
white-space, comments, and the inline-Z80 ISR. Uses `:::` to define a
border-cycling handler, `[']` to take its address, `IM2-HANDLER!` to
install, and `WAIT-FRAME` (which already implements `EI; HALT; DI`) as
the main loop body.

Tests in `tests/test_example_im2_rainbow.py` build the example to .sna,
load it through the simulator, and assert: 3 frames yield 3 ULA
interrupts; 8 consecutive frames produce border writes
`[1,2,3,4,5,6,7,0]` (one per frame, advancing); the JP slot at `$B9BA`
is populated with the ISR's address after install.

Fuse acceptance: deferred to manual confirmation. The simulator-level
test is a strong regression guard for the byte-level mechanism.

---

## Decisions that drifted from the original plan

**T-state cost split for `fire_interrupt`.** The plan said "add 13
T-states". The shipped implementation distinguishes 13 (IM 1) from 19
(IM 2 — extra cycles to read the vector). Better than the plan; matches
real hardware.

**`HALT` primitive interaction with IM 2.** The existing `HALT`
primitive emits a bare `halt` byte with no `dispatch` after it (its
docstring even says "execution stops"). On non-IM2 programs that's
fine; the run loop exits on `halted=True`. Under IM 2, a `BEGIN HALT
AGAIN` loop unhalts on interrupt and falls through into whatever
primitive's bytes happen to follow `HALT` in the blob — in our example
that was `BORDER`'s `LD A,L; OUT ($FE),A; POP HL; dispatch`, producing
a spurious `OUT ($FE),0` per frame.

The demo works around this by using the existing `WAIT-FRAME` primitive
(which is `EI; HALT; DI; ...; dispatch`) instead of inline `HALT`. A
proper fix — appending `dispatch` to `HALT` itself — was deliberately
deferred: it shifts every existing SNA's byte layout by 3 bytes per
HALT use site, which would break the plasma 48K golden-file regression
guard. The IM 2 milestone shouldn't bundle that change. Recommend a
follow-up PR that updates the golden file once.

**EI/DI as Forth primitives.** Added because `IM2-HANDLER!`
deliberately leaves EI to the caller, and the caller (a Forth colon
body) had no way to EI without dropping into `:::`. Trivially small
primitives (one byte + dispatch each); useful in their own right.

---

## Non-goals (kept from the plan)

- **Chained handlers.** Single handler slot. If two subsystems need
  ISR time, they share a hand-written dispatcher in user code.
- **NMI ($0066).** No use case in zt today.
- **R register modelling.** Not used by any current primitive; tracking
  it costs every opcode a counter increment for no benefit.
- **Cycle-accurate interrupt timing within a frame.** Auto-fire happens
  at T-state 0 of the new frame, not at the actual ULA top-of-frame
  moment. Adequate for music drivers and typical raster work;
  insufficient for precision multicolour. Documented.
- **Static-assert against allocations colliding with `$B800–$B9BB`.**
  The plan called for it, but the existing `$5B5C` (BANKM shadow)
  doesn't have analogous machinery either. Risk is low because zt heaps
  grow modestly from `$8000`. Add when introducing collision detection
  generally.
- **`--im2-table-page N` CLI override.** Not needed for AY work. Easy
  to add as a follow-up polish PR.

## Shipped after v1: Forth-level ISRs via the shim

`IM2-HANDLER!` now takes the xt of a `:` colon word. A built-in
shim (`__im2_shim__`) saves AF/HL/BC/DE/IX/IY on entry, dispatches into
a 4-byte mutable thread (`__im2_thread__`) holding `[user_xt,
__im2_exit_xt]`, and the user word's normal EXIT lands on the second
cell which calls the `__im2_exit__` primitive. That primitive restores
the saved state and finishes with `EI; RETI`.

Net effect: a frame ISR can be one line of plain Forth instead of a
register-saving Z80 routine. The motivating example went from a 50-line
`:::` body in `examples/im2-music` to a 3-line colon definition. The
shim adds ~140 T-states per fire on top of the user body — 0.2% of CPU
at 50 Hz. Power users wanting the raw path can hand-emit a `:::` ISR
and install its address by manually writing `$B9BA` (the JP slot
operand) instead of going through `IM2-HANDLER!`.

The constraint: the user word must be stack-neutral (`( -- )`) on both
the data stack and the return stack. The shim doesn't swap to a
private SP, so any imbalance leaks into the foreground's stacks.

---

## Sharp edges

**EI-after-instruction quirk.** Real Z80: an EI doesn't enable
interrupts until *after* the next instruction executes — this prevents
immediate re-entry. Modeled via `_ei_pending`, cleared after one step
in `run_until`. Without it, `EI; RET` from an ISR could re-fire before
the caller resumes.

**Interrupt-during-prefix.** ED, CB, DD, FD prefixes don't accept
interrupts mid-instruction. Handled by construction: `run_until` only
checks `_should_auto_fire` at the top of each iteration, never between
`_fetch` and `_exec_ed`/etc.

**Default deadline initialization.** `_next_int_at` is set to
`t_states_per_frame` at construction, not 0 — otherwise a fresh
machine would fire an interrupt on the first instruction. Easy to get
wrong; explicit test in `TestDefaultInterruptState`.

**`HALT` semantics under IM 2.** See "Decisions that drifted" above.
This is the one open issue worth picking up in a follow-up PR.

---

## Files touched summary

New:
- `src/zt/assemble/im2_table.py`
- `tests/test_sim_im_opcodes.py`
- `tests/test_sim_interrupts.py`
- `tests/test_forth_result_interrupts.py`
- `tests/test_im2_table.py`
- `tests/test_primitives_im2.py`
- `tests/test_example_im2_rainbow.py`
- `examples/im2-rainbow.fs`
- `docs/im2-architecture.md` (this file)

Modified:
- `src/zt/sim.py` — `iff2`/`i`/`im_mode`/`bus_byte`/frame fields,
  `fire_interrupt`, `run_until`, `_should_auto_fire`,
  `_tick_halt_wait`, EI-pending plumbing in `_op_ei`, seven new ED
  opcodes, `ForthResult.interrupt_count`
- `src/zt/assemble/opcodes.py` — `im_0/1/2`, `ld_i_a`, `ld_a_i`,
  `reti`, `retn`
- `src/zt/assemble/primitives.py` — `EI`, `DI`, `IM2-HANDLER!`,
  `IM2-HANDLER@`, `IM2-OFF`
- `src/zt/format/sna.py` — `im2_table=False` parameter on `build_sna`
  and `build_sna_128`, lazy injection via the helpers
- `src/zt/cli/main.py` — `_image_uses_im2(compiler)` helper, plumbed
  into both build call sites

---

## Ordering rationale

M1 unblocked M2's tests (no `LD I,A` → can't set up IM 2 in tests). M2
unblocked M4's tests (no `fire_interrupt()` → can't prove the handler
ran). M3 was independent and could parallelize. M4 layered on top of
all three. M5 closed the loop with a demo that exercises the full
stack.

Total IM 2 surface: 137 dedicated tests passing, 0 regressions across
the broader 3672-test suite.
