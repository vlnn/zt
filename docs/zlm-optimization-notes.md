# 2bit-dot+! Optimization Audit

## TL;DR

The `2BIT-DOT+!` primitive is the hot path for the tinychat chatbot —
60% of T-states across a HELLO→HI run. Several plausible
optimizations were evaluated against Zaks's *Programming the Z-80*
(2nd ed., 1980) and the included `tools/bench_tinychat.py`. Net: the
current implementation is already within ~5-10% of what's achievable
without restructuring zt's threaded interpreter or simulator. This
note records what was tried, what helped, and what's left on the
table — so the next round of work doesn't repeat the same paths.

## Baseline

`tools/bench_tinychat.py` runs the chatbot on `HELLO\r` and reports
T-state count for the first response cycle:

    ticks: 649,741,899  wall: 43.1s  HELLO and HI both on screen

Profile of where the cycles go (sampled with `zt.profile.core`):

    dot_plus_store_2bit  ~60% of T-states across the chat
    multiply             ~3%
    everything else      <3% per primitive

Per-MAC cost (439K MACs across the 4 layers × 3 inferences):
~1500 T-states reported. Using Zaks's published timings, the inner
muladd path is 100-130 T per MAC, plus ~150 T per group of 4 MACs of
outer-loop overhead — works out to ~175 T per MAC. The ~5x difference
between estimate and measurement is attributable to:

- The threaded-interpreter NEXT body costing 79 T-states per primitive
  call (`LD r,(IX+d)` is 19 T each on Z80, used twice in NEXT).
- Per-cell linear-cell wrapper costing ~1500 T per cell × 1848 cells
  per chat ≈ 2.7M T (~0.4%).
- Per-MAC overhead is harder to attribute precisely without
  cycle-accurate profiling — our profile has 100-instruction sample
  granularity, and inlined primitives blur word boundaries.

## Optimizations evaluated

### #1 — Inline `_2bdps_muladd` (LANDED)

Replaced the per-MAC `CALL`/`RET` (27 T overhead) with four inlined
copies via `_emit_inlined_muladd(a, sfx)`. Code size: +82 bytes.
Bench delta: **0.3% noise.** Code is cleaner; kept.

### #2 — Skip activation read on zero weight (LANDED, ~18% speedup)

Reorder: `cp 2; jr z, skip` before `push af; ld a,(bc); ...` so zero
weights skip the activation load entirely. The zero path becomes:
`and 03; cp 2; jr z, skip; ...; skip: inc bc; inc bc`.

**Real weight distribution in z80ai's tinychat** (extracted from
`model.npz`):

| Layer | -2  | -1   | 0      | +1   |
|-------|-----|------|--------|------|
| fc1   | 0.4%| 15.2%| 73.9%  | 10.6%|
| fc2   | 0.2%| 12.6%| 75.6%  | 11.5%|
| fc3   | 0.3%| 18.6%| 64.9%  | 16.2%|
| fc4   | 0.2%| 17.9%| 68.0%  | 13.9%|

72% of MACs become a 6-instruction skip (~45 T) instead of the full
~100 T baseline path. Per-MAC savings of ~55 T × 0.72 zero rate
× 432K MACs per HELLO→HI = ~17M T saved.

**Measured: 65.7M → 54.0M T-states for HELLO→HI = 17.9% faster.**

(An earlier attempt at this optimization was incorrectly judged
"2% slower" — that measurement was on a fixed-instruction-budget
bench window which spent most of its T-states in the post-chat
keyboard-poll loop, diluting the actual chat speedup. The correct
measurement stops the bench when "HI" first appears on screen.)

### #3 — Cache query partial sum across autoregressive steps

Estimated 1-3% based on saving half of fc1's MACs for 2 of 3 inference
steps. Not implemented. Would require splitting `encode-input` into
`encode-query` + `encode-context` and adding a 512-byte cache buffer.

### #4 + #5 — `linear-cell` as primitive, fold ReLU

Profile shows Forth dispatch is <3% of total. Maximum possible win
<3% regardless of implementation. Not pursued.

### #6 — Shadow registers (EXX) in the inner loop

Zaks confirms `EXX` = 4 T (Ch IV, p.255), `EX AF, AF'` = 4 T. Using
shadow HL' for `count` and shadow DE' for `wptr` would eliminate
4 × `LD HL,(nn)`/`LD (nn),HL` per group at 16 T each = 64 T saved,
minus 8 T for two EXX swaps = 56 T net per group. Across 36K groups
× 3 inferences = ~6M T-states (~0.9%).

Blocker: zt's assembler and simulator don't currently support EXX
(0xD9), EX AF AF' (0x08), or LD DE,(nn) (ED 5B nn nn). Adding all
three is ~1-2 hours of careful work — disproportionate for ~1% gain.

### Zaks's Improved Multiply Step 1 (Ch III, p.126)

Replace `DEC B; JP NZ, MULT` with `DJNZ MULT`. zt's assembler
*does* support DJNZ (`a.djnz_to(target)`). Blocker: in
`2BIT-DOT+!`, BC holds `aptr` and is consumed by `ld a,(bc); inc bc`
during the activation read. Freeing B for DJNZ requires moving aptr
to DE or HL — but DE is needed for the activation value (so `add
hl,de` works) and HL is the accumulator. The only alternatives (IX
or IY for aptr) cost 19 T per indexed read instead of 7 T for
`ld a,(bc)`, swamping the DJNZ savings. **Not feasible without a
deeper refactor.**

### Cache packed byte in A' via `EX AF, AF'`

Would eliminate 3 × (13 + 4 + 4 + 13) = 102 T per group of memory
traffic on `_2bdps_pkd` plus a few more on the final iteration.
Per-group net after EX AF AF' overhead: ~78 T saved. Across 36K
groups × 3 = ~8.4M T (~1.3%). Same blocker as #6 — needs simulator
and assembler support for opcode 0x08.

## What would actually move the needle

The model is dense; per-MAC throughput is the bound. Real
speedups (>1.5x) require one of:

1. **Sparse query/context dot product.** ~95% of input activations
   are zero (only ~7 nonzero query buckets after trigram hashing).
   Iterating over nonzero inputs and looking up *columns* of the
   weight matrix could give 10-20x on fc1's input half. Requires
   transposing the weight matrix and a different kernel —
   well-bounded but multi-day.

2. **Self-modifying inner loop.** Patch the activation address as
   an immediate operand each MAC; saves the indirect load cycles.
   Aggressive but proven on the demoscene.

3. **Switch the threaded interpreter from IX-based IP to BC-based**
   (Camel Forth style). NEXT becomes `LD A,(BC)/INC BC/...` which
   is 26 T instead of 58 T for the IP fetch. Saves ~32 T per
   primitive call × ~100K calls per chat = 3.2M T (~0.5%) — but only
   inside primitives; doesn't help the dot product directly. Major
   refactor; affects every primitive that uses BC.

## Verifying timings against Zaks

Quick reference — instructions used in `2BIT-DOT+!`, with the page
numbers in the 2nd edition where the per-instruction reference page
appears:

| Instruction       | T-states | Zaks page |
|-------------------|----------|-----------|
| `LD HL, (nn)`     | 16       | 334       |
| `LD (nn), HL`     | 16       | (companion) |
| `LD A, (nn)`      | 13       | 318       |
| `LD (nn), A`      | 13       | 317       |
| `LD r, (IX+d)`    | 19       | 305       |
| `INC IX`          | 10       | 272       |
| `INC ss`          | 6        | 264       |
| `ADD HL, ss`      | 11       | 203       |
| `SBC HL, ss`      | 15       | 422       |
| `PUSH qq`         | 11       | 379       |
| `POP qq`          | 10       | 373       |
| `CALL nn`         | 17       | 222       |
| `RET`             | 10       | (in instr summary) |
| `DJNZ` (taken)    | 13       | 245       |
| `DJNZ` (not)      | 8        | 245       |
| `EXX`             | 4        | 256       |
| `EX AF, AF'`      | 4        | (companion) |

These match what the simulator uses (`zt.assemble.opcodes`).

## Tooling

- `tools/bench_tinychat.py` — pinned benchmark, asserts HELLO→HI on
  screen, reports T-state count and wall time.
- `tests/test_2bit_dot_plus_store.py` — 20-test correctness oracle
  for the primitive; run after any edit.
- `zt build --profile` — emits a per-word T-state report; useful for
  attributing work but slow. Use a small `max_ticks` budget.
