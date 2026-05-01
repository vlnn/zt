# Getting started

zt is a Forth-to-Z80 cross-compiler: write `.fs`, get a ZX Spectrum
`.sna` snapshot that runs in Fuse, ZEsarUX, or a real 48K via divMMC.
This is the 60-second tour; the [README](../README.md) has the depth.

## Install

zt is a [uv](https://docs.astral.sh/uv/)-managed Python project. Clone
it, then:

```
uv sync       # create the project venv, install dependencies
make test     # verify the toolchain (green = good)
```

From here you can run `zt` two ways:

- **Through uv, from inside the checkout** (recommended for hacking on zt):
  ```
  uv run zt build foo.fs -o foo.sna
  ```
- **As a system-wide command** (recommended if you just want to use zt):
  ```
  uv tool install .             # one-time, exposes `zt` on your PATH
  zt build foo.fs -o foo.sna    # from anywhere
  ```

The rest of this guide uses the `uv run zt` form; drop the `uv run`
prefix if you installed it globally.

## Build the bundled examples

```
make examples
```

`build/*.sna` are then ready to load. Try `build/plasma.sna` first —
QAOP / 6789 to pan a colour plasma across the attribute area.

## Your first program

```forth
\ hello.fs
: greet   ." HELLO SPECTRUM" cr ;
: main    7 0 cls greet begin again ;
```

```
uv run zt build hello.fs -o hello.sna --map hello.map
```

Load `hello.sna` in Fuse, ZEsarUX, or a real 48K. White background,
black text, idle loop. The `.map` gives your debugger Forth word names
instead of raw addresses.

## Where to go next

- [`forth-style.md`](forth-style.md) — how to write Forth that fits
  the grain of this codebase: factoring, naming, stack effects, when
  to reach for `::` or `:::`. **Read this before writing much.**
- [`primitives.md`](primitives.md) — every Z80 primitive the compiler
  exposes, with stack effects.
- [`asm-words.md`](asm-words.md) — the `:::` assembler-word reference.
- [`128k-architecture.md`](128k-architecture.md) — banking, paged
  code, and the `--target 128k` story.
- [README Part 2](../README.md#part-2--how-it-works-internal-reasoning) —
  execution model, `NEXT` dispatch, IR pipeline, optimization passes.
- `examples/plasma4/` → `examples/arkanoid/` → `examples/mined-out/` —
  increasing complexity, in that order.
