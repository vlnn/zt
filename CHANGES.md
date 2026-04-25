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

All three are registered in `PRIMITIVES` and on the `INLINABLE_PRIMITIVES`
whitelist (except `2BIT-DOT+!`, which has internal jumps and a loop).

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

Run: `uv run python -m zt.cli profile --source examples/zlm-smoke/main.fs --max-ticks 200000 --words row-mac,row-mac-fast,row-mac-dot`

## Files in this zip

```
src/zt/assemble/inline_bodies.py
src/zt/assemble/opcodes.py
src/zt/assemble/primitives.py
src/zt/sim.py
tests/test_unpack_primitives.py
tests/test_2bit_muladd.py
tests/test_2bit_dot_plus_store.py
examples/zlm-smoke/main.fs
```

Drop them into your zt tree at the matching paths to apply.
