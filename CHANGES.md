# Changes

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
