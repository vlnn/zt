# `zt` command-line reference

The `zt` executable has four subcommands:

| Subcommand    | Purpose                                                  |
|---------------|----------------------------------------------------------|
| `zt build`    | Compile a `.fs` source file to a Spectrum image          |
| `zt inspect`  | Decompile a `.fsym` symbol dump back to threaded Forth   |
| `zt test`     | Discover and run `test-*` words from `.fs` files         |
| `zt profile`  | Run a compiled program in the simulator and report timings |

Run `zt <sub> --help` for the canonical flag list. This doc is the
narrative companion: when each flag matters, what the output looks like,
and how the subcommands compose.

`zt` reads no environment variables and no config files. Every knob is
either a flag or an argument.

---

## `zt build` — compile to a snapshot

```
zt build SOURCE -o OUTPUT [options]
```

Takes one `.fs` entry point and writes one image. Output format is
auto-detected from the extension; pass `--format` to override.

```
zt build hello.fs -o hello.sna --map hello.map
```

### Output formats

| Extension | `--format` | Target           | Notes |
|-----------|------------|------------------|-------|
| `.sna`    | `sna`      | 48K and 128K     | 49,179 bytes (48K) or 131,103 bytes (128K) |
| `.z80`    | `z80`      | 128K only        | v3 format with explicit machine-type byte; preferred for 128K |
| `.bin`    | `bin`      | raw image        | no header, no padding — just the assembled bytes |

`.tap` is **not** supported (see `docs/PLAN.md` "Pending").

For the 48K-vs-128K, `.sna`-vs-`.z80` decision matrix, see
[`128k.md`](128k.md).

### Memory layout

| Flag                | Default (48K) | Default (128K) | Effect |
|---------------------|---------------|----------------|--------|
| `--origin ADDR`     | `0x8000`      | `0x8000`       | First byte of the compiled image |
| `--dstack ADDR`     | `0xFF00`      | `0xBF00`       | Data-stack top — grows down |
| `--rstack ADDR`     | `0xFE00`      | `0xBE00`       | Return-stack top — grows down |
| `--target {48k,128k}` | `48k`       | —              | Switches defaults and enables banking primitives |
| `--paged-bank N`    | n/a           | `7`            | Bank at `$C000` at startup; 0–7 |
| `--border N`        | `7`           | `7`            | Initial border colour stored in the snapshot header |

Address values accept any Python-int literal: `0x8000`, `32768`, `0o100000`.

128K builds reject stack values inside `$C000–$FFFF` because the paged
slot would swap them out on the next `BANK!`. The CLI reports the issue
and exits non-zero.

### Includes and the bundled stdlib

| Flag                  | Default     | Effect |
|-----------------------|-------------|--------|
| `--include-dir PATH`  | (none)      | Extra search root for `INCLUDE`/`REQUIRE`; repeatable |
| `--stdlib`            | on          | Prepend `src/zt/stdlib/core.fs` automatically |
| `--no-stdlib`         | off         | Skip the auto-prepend (size-budgeted images, ZLM) |

`INCLUDE` and `REQUIRE` already search the directory of the file doing
the including, so within a project layout you rarely need
`--include-dir`. It exists for cross-project shared libraries.

Beyond `core.fs`, additional stdlib modules (`screen.fs`, `input.fs`,
`sound.fs`, `bit.fs`, `fixed.fs`, `grid.fs`, `hiscore.fs`, `logic.fs`,
`rand.fs`, `sprites.fs`, `udg.fs`, `trail.fs`, `ay.fs`) sit in
`src/zt/stdlib/` and are pulled in on demand via `REQUIRE name.fs` —
the bundled stdlib dir is always on the include path.

### Optimisation

| Flag                       | Default | Effect |
|----------------------------|---------|--------|
| `--no-optimize`            | off     | Disable the peephole optimizer |
| `--inline-next`            | on      | Inline the `NEXT` dispatch body into every primitive (~10% speedup, ~500 bytes larger) |
| `--no-inline-next`         | off     | One shared `NEXT`, primitives end with `JP NEXT` |
| `--inline-primitives`      | on      | Inline pure-primitive colon bodies into callers |
| `--no-inline-primitives`   | off     | Keep colon dispatch even for inlinable bodies |
| `--tree-shake`             | off     | Strict tree-shake: fail rather than fall back |
| `--no-tree-shake`          | off     | Force the eager build for layout-sensitive tooling |

With neither tree-shake flag, the compiler auto-tree-shakes when it
can and falls back to the eager build with a stderr warning when it
can't. This is what `make examples` uses. Pass `--tree-shake` in CI
to gate against accidental fallbacks.

`--no-inline-next` matters for the 48K ZLM port — the flag was
discovered to be necessary to fit `examples/zlm-tinychat-48k/` under
the recommended `--origin 0x5C00` layout.

### Debug artefacts

| Flag             | Output                                                       |
|------------------|--------------------------------------------------------------|
| `--map PATH`     | Symbol map for an emulator (`$ADDR name` per line)           |
| `--map-format`   | `fuse` or `zesarux`; default auto from extension             |
| `--sld PATH`     | sjasmplus Source-Level-Debug for ZEsarUX line stepping       |
| `--fsym PATH`    | JSON dictionary dump for `zt inspect` and external tooling   |

Map-format auto-detection by extension: `.map → fuse`,
`.sym → zesarux`, `.zesarux → zesarux`, anything else → `fuse`.
Override with `--map-format` when the convention disagrees with you.

```
zt build prog.fs -o prog.sna --map prog.map --fsym prog.fsym --sld prog.sld
```

Three artefacts is the usual recipe: the `.map` is what your emulator
loads, the `.sld` is what gives you line-by-line stepping in ZEsarUX,
and the `.fsym` is what `zt inspect` reads. `.map` and `.sld` can be
omitted if you only want host-side decompilation.

### Inline profiling

| Flag                     | Default            | Effect |
|--------------------------|--------------------|--------|
| `--profile`              | off                | Run the built image and write a profile report |
| `--profile-output PATH`  | `<output>.prof`    | Where the report goes |
| `--profile-ticks N`      | `1_000_000`        | Instruction budget for the profile run |

This is `zt build` + `zt profile` in one shot, equivalent to building
then immediately running `zt profile --image <output>.sna`. Useful in
a `make` target where every build refreshes its companion profile.
For interactive comparison and baselining, use `zt profile` directly
(below).

### Build-line summary

```
prog.fs -> prog.sna [sna] (1066 bytes code, 12 words, 49179 bytes output)
```

`code` is the compiled threaded image; `words` is the colon count after
optimisation; `output` is the file size on disk including the snapshot
header (smaller for `.bin`).

---

## `zt inspect` — decompile a `.fsym`

```
zt inspect --symbols PATH [--image PATH]
```

Walks every colon definition in the `.fsym` JSON and prints a
threaded-code listing with names, not addresses.

```
$ zt inspect --symbols hello.fsym
: cls  ( $8175 )
    swap 3 lshift or 22528 768 rot fill 16384 6144 zero fill reset-cursor ;

: cr  ( $816A )
    13 emit ;

: greet  ( $819E )
    lit <_str_0> 5 type cr ;

: main  ( $81AF )
    7 zero cls greet halt ;
```

Without `--image`, string literals show as `<_str_0>` placeholders. Pass
`--image PATH` (typically the matching `.bin` from the same build) to
have the decompiler reach into the bytes and reconstruct the actual
string.

The output is **not** valid Forth source. It's a debugging view —
parens hold addresses for grep, primitive names match the threaded
cells one-to-one, and there's no attempt to reconstruct stack-effect
comments. For production debugging, pair this with the `.map` loaded
into your emulator: emulator at `$A247` → `grep A247 prog.map` →
inspect output gives you the body that lives there.

`zt inspect` reads the `.fsym`'s JSON directly; nothing has to be
loaded into a simulator. You can ship the `.fsym` separately from the
`.sna` and inspect off-machine.

---

## `zt test` — run Forth `test-*` words

```
zt test [SPEC ...] [-k PATTERN] [-v] [-x] [--max-ticks N]
```

Discovers every `: test-<name> ... ;` word in `.fs` files matching
`test_*.fs`, compiles each with a synthetic `: main test-<name> halt ;`
prologue, runs it under the simulator, and aggregates the results.

The mechanism, the `assert-eq` / `assert-true` / `assert-false`
vocabulary, the ambient include-dir behaviour, and the equivalent
pytest-collector setup all live in
[`FORTH-TEST-INTEGRATION.md`](FORTH-TEST-INTEGRATION.md). This section
just covers the CLI surface.

### Specs

The positional `SPEC` argument can take any of these forms; mix freely:

```
zt test                                     # discover from cwd
zt test tests/                              # discover under a directory
zt test tests/test_arith.fs                 # one whole file
zt test tests/test_arith.fs::test-plus      # one specific word
zt test tests/test_arith.fs tests/test_string.fs  # multiple, mixed
```

Default scope is the current directory. Discovery is recursive within
each given directory.

### Filtering and stopping

| Flag             | Effect |
|------------------|--------|
| `-k PATTERN`     | Only run tests whose word name contains PATTERN (substring, case-sensitive) |
| `-x`             | Stop on the first failure |
| `--max-ticks N`  | Per-test instruction budget; default 1,000,000 |

`-k` happens after spec expansion: `zt test tests/ -k abs` discovers
every test under `tests/` then runs only those whose names contain
`abs`. The `FILE::WORD` form is exact, so it's the right tool when you
know which test you want.

### Output

Default is dot-progress with a failure summary:

```
$ zt test tests/test_arith.fs
..F

FAILED tests/test_arith.fs::test-broken
  expected: 4
  actual:   3
2 passed, 1 failed
```

`-v` switches to one line per test:

```
$ zt test -v tests/test_arith.fs
tests/test_arith.fs::test-plus PASSED
tests/test_arith.fs::test-minus PASSED
tests/test_arith.fs::test-broken FAILED


FAILED tests/test_arith.fs::test-broken
  expected: 4
  actual:   3
2 passed, 1 failed
```

Exit code is `0` when every selected test passed, `1` otherwise. Wire
the same check into `make test` or CI.

### When to use this vs. pytest

`zt test` is the right harness when there's no Python around — pure
Forth project, scripted CI step, deployment artefact verification.

When the project already has Python tests, prefer the pytest collector
in `conftest.py` (root of this repo). It picks up the same `test-*`
words via `zt.test_runner.compile_and_run_word`, runs them as pytest
items, and lets `pytest -k`, `pytest -x`, `pytest -vv` and parametrised
Python tests share a single test runner. See
[`FORTH-TEST-INTEGRATION.md`](FORTH-TEST-INTEGRATION.md) for the
drop-in `conftest.py`.

---

## `zt profile` — measure where the cycles go

```
zt profile (--source SRC | --image IMAGE) [options]
```

Runs a compiled program inside the simulator with cycle-accurate timing
and prints a per-word T-state breakdown. Either point it at source
(compile-then-run) or at a built `.sna` (with a sibling `.map` for
symbol resolution).

```
zt profile --source examples/hello.fs --max-ticks 100000 --words emit,cr,type
```

### Input modes

| Flag             | Effect |
|------------------|--------|
| `--source PATH`  | Compile `.fs` and profile the result |
| `--image PATH`   | Profile a pre-built `.sna` |
| `--symbols PATH` | Override the symbol file (default: sibling `.map` next to `--image`) |

`--source` is the development-loop mode — change a primitive, re-profile,
see the delta. `--image` is the CI mode — bench against an artefact
that was built once and pinned.

For `--image`, the sibling `.map` resolves addresses to word names. If
the map isn't next to the image, point `--symbols` at it explicitly.
Without symbols, words show as `<unknown>` for non-primitive bodies.

### Run controls

| Flag              | Effect |
|-------------------|--------|
| `--max-ticks N`   | Instruction budget; default 1,000,000 |
| `--words A,B,C`   | Limit the report to specific word names (comma-separated) |

`--max-ticks` is a host-side cap on the simulator step count, not Z80
T-states. Bigger programs need a bigger budget; the CLI runs to the
program's `HALT` or to the budget, whichever comes first.

`--words` filters the report. The full profile is always computed —
filtering only affects what gets printed. Useful when comparing one
hot path across a baseline.

### Reports

Default text output:

```
Word                  Calls     Self   Self%       Incl   Incl%      Avg
------------------------------------------------------------------------
type                     49    68546    6.4     920986   86.1    18795
emit                    978   524477   49.0     919005   85.9      939
cr                       48      816    0.1     909782   85.1    18953

Total: 1069450 T-states across 100000 instructions
```

`Self` is T-states executed directly inside the word's body. `Incl` is
self plus everything called. `Self%` and `Incl%` are fractions of the
total run. `Avg` is `Incl` divided by `Calls`, useful for spotting
words that are slow per-invocation even if their total share is
modest.

`--json` swaps the text table for a machine-readable JSON report on
stdout — pipe it through `jq` for scripting or store snapshots
alongside benchmarks.

### Saving and comparing baselines

| Flag                    | Effect |
|-------------------------|--------|
| `--save PATH`           | Write `PATH.prof` (text) and `PATH.zprof` (JSON snapshot) |
| `--baseline PATH.zprof` | Compare the current run against a saved snapshot |
| `--fail-if-slower PCT`  | Exit non-zero if any selected word regressed by more than `PCT%` |

The typical optimisation loop:

```
zt profile --source prog.fs --save baseline           # snapshot before
# edit prog.fs
zt profile --source prog.fs --baseline baseline.zprof --words HOT-WORD
```

The baseline diff prints `Base Incl`, `Curr Incl`, `Δ`, and `Δ%`
columns sorted by absolute delta. Words missing from one side are
shown with a placeholder; sign convention is "positive Δ = slower
now."

For CI, combine `--baseline` with `--fail-if-slower 5` so any selected
word regressing by more than 5% fails the build. The result composes
naturally as a `make bench` recipe:

```make
.PHONY: bench
bench: build/prog.sna baseline.zprof
	zt profile --image $< --baseline baseline.zprof \
	    --words inner-loop,blit --fail-if-slower 5
```

---

## How the subcommands compose

A typical end-to-end session uses three of the four:

```
zt build prog.fs -o prog.sna --map prog.map --fsym prog.fsym
zt test  tests/                                 # run unit tests
zt profile --image prog.sna --save bench        # snapshot perf
# ... edit ...
zt profile --image prog.sna --baseline bench.zprof --fail-if-slower 5
zt inspect --symbols prog.fsym                  # eyeball the threaded code
```

`zt build --profile` collapses the build-and-snapshot step into one
invocation. `zt build --tree-shake` plus `zt test -x` is a useful
sanity gate before pushing.

---

## See also

- [`getting-started.md`](getting-started.md) — install and first-program walkthrough
- [`128k.md`](128k.md) — `--target 128k`, the format choice, and stack placement
- [`FORTH-TEST-INTEGRATION.md`](FORTH-TEST-INTEGRATION.md) — the testing protocol shared by `zt test` and the pytest collector
- [`im2-architecture.md`](im2-architecture.md) — interrupt-mode-2 plumbing that liveness gates into the build automatically
- [`primitives.md`](primitives.md) — what's actually compiled into every image
