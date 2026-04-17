# Forth Test Integration with pytest — Implementation Summary

## Overview

Custom pytest collector that discovers `.fs` test files and exposes each
`: test-*` word as an individual pytest item. Full `-v`, `-k`, `-x`, `--tb`
compatibility.

## Prerequisites

- M1.5 (Z80 simulator) — run compiled images
- M2 (tokenizer) — parse Forth source
- M3 (compiler core) — compile Forth to threaded code

## Forth-side conventions

### Test file naming

`tests/forth/test_*.fs` — mirrors pytest's Python discovery.

### Test word naming

Any word starting with `test-` is collected as a test item.

```forth
\ tests/forth/test_arith.fs
include test-lib.fs

: test-plus       3 4 +   7 assert-eq ;
: test-negate     5 negate -5 assert-eq ;
: test-2dup       3 5 2dup + -rot +  8 assert-eq  8 assert-eq ;
```

### Test library (`stdlib/test-lib.fs`)

```forth
\ Result protocol — fixed memory addresses
\ $FF80: 0 = pass, nonzero = fail
\ $FF82: expected value (on failure)
\ $FF84: actual value (on failure)

variable _result    \ at a known compiled address — Python reads $FF80
variable _expected  \ $FF82
variable _actual    \ $FF84

: assert-eq  ( actual expected -- )
    over = if
        2drop
    else
        _expected !
        _actual !
        1 _result !
    then ;

: assert-true  ( flag -- )
    if else 1 _result ! then ;

: assert-false  ( flag -- )
    if 1 _result ! then ;
```

**Note:** The fixed addresses ($FF80–$FF85) are a convention between
`test-lib.fs` and the Python harness. The compiler must place these
variables at known locations, or the Python side must look up their
addresses from the symbol map after compilation.

**Better alternative:** Compile once, read variable addresses from
`compiler.words` dictionary, then use those addresses to inspect
simulator memory. No hardcoded addresses needed.

## Python-side implementation

### File layout

```
tests/
├── conftest.py              # pytest_collect_file hook
├── forth_runner.py           # compile-and-run helpers
├── forth/
│   ├── test_arith.fs
│   ├── test_stack.fs
│   ├── test_logic.fs
│   ├── test_memory.fs
│   └── test_controlflow.fs  # available after M4
```

### conftest.py — collector

```python
import re
import pytest
from tests.forth_runner import compile_and_run_word

TEST_WORD_RE = re.compile(r"^:\s+(test-\S+)", re.MULTILINE)


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".fs" and file_path.name.startswith("test_"):
        return ForthFile.from_parent(parent, path=file_path)


class ForthFile(pytest.File):
    def collect(self):
        text = self.path.read_text()
        for match in TEST_WORD_RE.finditer(text):
            name = match.group(1)
            yield ForthItem.from_parent(self, name=name, source=text)


class ForthItem(pytest.Item):
    def __init__(self, name, parent, source):
        super().__init__(name, parent)
        self._source = source

    def runtest(self):
        result = compile_and_run_word(self._source, self.name)
        if result.failed:
            raise ForthAssertionError(
                test_word=self.name,
                expected=result.expected,
                actual=result.actual,
            )

    def repr_failure(self, excinfo, style=None):
        e = excinfo.value
        lines = [f"Forth assertion failed in `{e.test_word}`"]
        if e.expected is not None:
            lines.append(f"  expected: {e.expected}")
            lines.append(f"  actual:   {e.actual}")
        return "\n".join(lines)

    def reportinfo(self):
        return self.path, None, f"forth: {self.name}"


class ForthAssertionError(Exception):
    def __init__(self, test_word, expected=None, actual=None):
        self.test_word = test_word
        self.expected = expected
        self.actual = actual
```

### forth_runner.py — compile and execute

```python
@dataclass
class ForthTestResult:
    failed: bool
    expected: int | None = None
    actual: int | None = None


def compile_and_run_word(source: str, test_word: str) -> ForthTestResult:
    """Compile source, build a main that calls one test word, run in simulator."""
    main_source = f"{source}\n: main {test_word} halt ;\n"

    compiler = make_compiler()
    compiler.compile_source(main_source)
    image = compiler.build()

    sim = Z80Simulator()
    sim.load(image, origin=ORIGIN)
    sim.run(max_cycles=1_000_000)

    result_addr = compiler.words["_result"].address
    expected_addr = compiler.words["_expected"].address
    actual_addr = compiler.words["_actual"].address

    flag = sim.read_word(result_addr)
    if flag == 0:
        return ForthTestResult(failed=False)

    return ForthTestResult(
        failed=True,
        expected=sim.read_word(expected_addr),
        actual=sim.read_word(actual_addr),
    )
```

## Example pytest output

```
$ uv run pytest tests/forth/ -v

tests/forth/test_arith.fs::test-plus PASSED
tests/forth/test_arith.fs::test-negate PASSED
tests/forth/test_arith.fs::test-abs-neg PASSED
tests/forth/test_arith.fs::test-abs-pos FAILED
tests/forth/test_stack.fs::test-dup PASSED
tests/forth/test_stack.fs::test-swap PASSED
tests/forth/test_stack.fs::test-rot PASSED

FAILED tests/forth/test_arith.fs::test-abs-pos
  Forth assertion failed in `test-abs-pos`
    expected: 7
    actual:   -7
```

Works with all standard pytest flags:

- `pytest tests/forth/ -k "arith"` — run only arithmetic tests
- `pytest tests/forth/ -x` — stop on first failure
- `pytest tests/forth/test_stack.fs::test-rot` — run single test word
- `pytest tests/ -v` — runs Python AND Forth tests together

## Multiple assertions per test word

The simple protocol above reports only the first failure per word.
For multiple assertions, extend the protocol with a failure log:

```forth
\ Reserve a failure log: up to 8 failures, 6 bytes each (id, expected, actual)
\ _fail_count at $FF80, log starts at $FF82

create _fail_log 48 allot
variable _fail_count
variable _assert_id

: next-assert  1 _assert_id +! ;

: assert-eq  ( actual expected -- )
    next-assert
    over = if
        2drop
    else
        _fail_count @ 8 < if
            _fail_count @ 6 * _fail_log +
            dup _assert_id @ swap !      \ store assert id
            dup 2 + rot swap !           \ store expected
            4 + !                        \ store actual
            1 _fail_count +!
        else
            2drop
        then
    then ;
```

Python side reads `_fail_count`, then walks the log to build
a list of `(assert_id, expected, actual)` tuples for reporting.

## Milestone placement

Implement after M3 (compiler core), alongside M4 (control flow):

1. Write `test-lib.fs` with `assert-eq`, `assert-true`, `assert-false`
2. Write `forth_runner.py` with `compile_and_run_word`
3. Write `conftest.py` collector (ForthFile, ForthItem)
4. Add first test files: `test_arith.fs`, `test_stack.fs`
5. Expand test coverage as new features land (control flow in M4, I/O in M5)

The Forth test suite grows alongside the compiler — each new feature
gets tested both from Python (unit/byte-level) and from Forth
(behavioral/integration).
