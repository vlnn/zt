# Forth tests

`.fs` files named `test_*.fs` can be run two ways:

- `zt test` — CLI runner. Works in any project that has `zt` installed.
- `pytest` — pytest collector. Works in projects that already use Python tests.

Each `: test-<n>` word becomes one test. The two runners share the same
discovery logic, the same test library, and the same assertion protocol.

## Writing a test file

```forth
include test-lib.fs

: test-plus    3 4 +       7 assert-eq ;
: test-abs     -5 abs      5 assert-eq ;
: test-zero?   0 0=          assert-true ;
```

Any word beginning with `test-` is picked up. Words without the prefix are
compiled but not run as tests, so helpers are fine:

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

On failure, `assert-eq` records both the expected and actual values so the
runner can show them. `assert-true`/`assert-false` record the failure flag
without values.

## Ambient include-dir

The directory a `.fs` test file lives in is added to the include path
automatically. A project shaped like this:

```
myproject/
├── lib/
│   └── math.fs
└── tests/
    └── test_math.fs
```

can `include ../lib/math.fs` from `tests/test_math.fs` without extra config.
Both `zt test` and the pytest collector apply this rule.

## Running with `zt test`

```bash
zt test                                     # discover from cwd
zt test tests/                              # discover from a directory
zt test tests/test_arith.fs                 # one file
zt test tests/test_arith.fs::test-plus      # one word
zt test -k "abs or negate"                  # substring filter on names
zt test -v                                  # one line per test
zt test -x                                  # stop on first failure
zt test --max-ticks 5000000                 # per-test tick budget
```

Default output:

```
...F.
FAILED tests/test_arith.fs::test-abs-pos
  assertion failed
  expected: 7
  actual:   -7
4 passed, 1 failed
```

Exit code is 0 when every selected test passes, 1 otherwise.

## Running with pytest

Drop this `conftest.py` into your `tests/` directory:

```python
from zt.testing import ForthTestResult, TEST_WORD_RE, compile_and_run_word
import pytest


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".fs" and file_path.name.startswith("test_"):
        return ForthFile.from_parent(parent, path=file_path)


class ForthFile(pytest.File):
    def collect(self):
        source = self.path.read_text()
        for match in TEST_WORD_RE.finditer(source):
            yield ForthItem.from_parent(self, name=match.group(1), source=source)


class ForthItem(pytest.Item):
    def __init__(self, *, name, parent, source):
        super().__init__(name, parent)
        self._source = source

    def runtest(self):
        result = compile_and_run_word(
            self._source, self.name,
            extra_include_dirs=[self.path.parent],
        )
        if result.failed:
            raise AssertionError(
                f"{self.name}: expected {result.expected}, got {result.actual}"
            )

    def reportinfo(self):
        return self.path, None, f"forth: {self.name}"
```

Then all pytest flags work: `-v`, `-k`, `-x`, `--tb=short`, `::test-word`
selectors, and Python tests in the same directory run alongside.

## How it works

`zt.testing.compile_and_run_word(source, word)` is the core primitive. It:

1. Compiles the source plus a synthetic `: main <word> halt ;`.
2. Loads the image into the simulator and runs until halt.
3. Reads `_result`, `_expected`, `_actual` from simulator memory via
   `compiler.words[name].data_address`. No fixed-address convention — the
   symbol table handles it.

The three protocol variables are plain `variable` declarations in
`test-lib.fs`. `_result` is 0 for pass, non-zero for fail. On failure,
`_expected` and `_actual` carry the operands of the failing assertion.

## Limitations

- **One failure per word.** After the first failing assertion in a word,
  subsequent assertions in the same word still execute but don't change
  the reported failure. Prefer one assertion per `test-` word.
- **Full-file recompile per test.** Each test word causes one compile of
  the whole file. Fine for dozens of tests per file; past hundreds, cache
  the image and rewrite only the `main` body cell between runs.
- **No fixtures, no Forth-side parametrization.** Parametrize by writing
  multiple `test-` words, or drive the same Forth source from a
  parametrized Python test.
