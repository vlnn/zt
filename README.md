# zt — Z80 Forth cross-compiler

Cross-compiles Forth to Z80 threaded code targeting the ZX Spectrum.

## Quick start

```
uv sync
uv run zt build output.sna
```

Load `output.sna` in Fuse, ZEsarUX, or any Spectrum emulator.

## Development

```
uv run pytest
```

## Architecture

- **DTC inner interpreter** — IX as IP, SP as data stack, IY as return stack, HL as cached TOS
- **Host-side dictionary** — no dictionary in the target image
- **Python cross-compiler** — `.fs` source files compile to raw threaded code
