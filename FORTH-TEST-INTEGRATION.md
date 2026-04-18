# Forth tests with pytest

`.fs` files named `test_*.fs` are collected by pytest and run as first-class
test items. Each `: test-<n>` word becomes one test ID; pytest's `-v`, `-k`,
`-x`, `--tb`, and `::test-word` selectors all work.

## Where tests live

```
tests/
├── conftest.py          ← collector
├── forth_runner.py      ← compile-and-run helper
└── forth/
    ├── test_arith.fs
    └── test_stack.fs
```

Anywhere under `tests/` works — the collector matches any `.fs` file whose
name starts with `test_`, at any depth. The `tests/forth/` subdirectory is a
convention, not a requirement.

## Writing a test file

```forth
include test-lib.fs

: test-plus    3 4 +       7 assert-eq ;
: test-abs     -5 abs      5 assert-eq ;
: test-zero?   0 0=          assert-true ;
```

Any word beginning with `test-` is picked up. Words without the prefix are
compiled but not run as tests, so feel free to define helpers:

```forth
include test-lib.fs

: double  dup + ;

: test-double-five   5 double   10 assert-eq ;
: test-double-zero   0 double    0 assert-eq ;
```

## Assertions

`stdlib/test-lib.fs` provides three:

| Word           | Stack effect              | Fails when          |
|----------------|---------------------------|---------------------|
| `assert-eq`    | `( actual expected -- )`  | `actual ≠ expected` |
| `assert-true`  | `( flag -- )`             | flag is zero        |
| `assert-false` | `( flag -- )`             | flag is non-zero    |

On failure, `assert-eq` records both the expected and actual values so
pytest can show them in the report. `assert-true`/`assert-false` record
the failure without values.

## Running tests

```bash
uv run pytest tests/forth/                           # all Forth tests
uv run pytest tests/forth/test_arith.fs              # one file
uv run pytest tests/forth/test_arith.fs::test-plus   # one word
uv run pytest tests/forth/ -k "abs or negate"        # filter by name
uv run pytest tests/ -v                              # Python + Forth, verbose
```

Failure output:

```
tests/forth/test_arith.fs::test-abs-pos FAILED

Forth assertion failed in `test-abs-pos`
  expected: 7
  actual:   -7
```

## How it works

The collector discovers `: test-<n>` definitions with a regex
(`^\s*:\s+(test-\S+)`) and yields one pytest item per match. For each
item, `compile_and_run_word(source, word_name)` does:

1. Compile the entire `.fs` file plus a synthetic `: main <word> halt ;`.
2. Load the image into the `Z80` simulator and run until halt.
3. Read `_result`, `_expected`, `_actual` from simulator memory via
   `compiler.words[name].data_address` — no fixed memory convention, the
   addresses come from the symbol table after compilation.

The three protocol variables are plain `variable` declarations in
`test-lib.fs`. `_result` is 0 for pass, non-zero for fail. On failure,
`_expected` and `_actual` carry the operands of the failing assertion.

## Limitations

- **One failure per word.** After the first failing assertion in a word,
  subsequent assertions in the same word still execute but don't change
  the reported failure. If you want multi-assertion reporting, switch to
  one assertion per `test-` word — that's the idiomatic pattern anyway.
- **Full-file recompile per test.** Each test word causes one compile of
  the whole file. Fine for dozens of tests per file; if a single file
  grows to hundreds, cache the image and rewrite only the `main` body
  cell between runs.
- **No fixtures, no Forth-side parametrization.** Parametrize by writing
  multiple `test-` words, or drive the same Forth source from a
  parametrized Python test if you need real parametrization.
