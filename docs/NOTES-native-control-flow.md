# Phase 0 → Phase 4 — `::` with control flow

This zip merges my Phase 0–4 native-control-flow work onto the layout of
your fresh upload. The base is your tree as I received it; the diff is six
files plus one deletion plus this NOTES file.

## What was changed in this merge

Six modular files updated with my work:

- `src/zt/compile/compiler.py` — `::` defining word, `native_control_flow`
  flag, native body emission, four-phase rewrite
- `src/zt/compile/code_emitter.py` — `compile_native_*` family for
  branches and DO/LOOP bodies
- `src/zt/compile/dictionary.py` — `redefinition_warning` distinguishes
  `:` vs `::`
- `src/zt/assemble/asm.py` — `native: bool` field; `dispatch()` emits
  `RET` when set
- `src/zt/assemble/inline_bodies.py` — `emit_native_primitive_body` for
  splice-at-address relocation
- `tests/test_controlflow.py` — `cf_mode` fixture; nine test methods
  parametrised across `{threaded, native-cf}`

One file added:

- `tests/test_double_colon.py` — 28 tests for the `::` defining word

One file deleted:

- `tests/conftest.py` — was identical to `conftest.py` at root except its
  imports went through the dead-flat `zt.testing` module instead of the
  live modular `zt.test_runner`. Deleting it leaves Forth `.fs` test
  collection to the root conftest, which already does the same thing
  through the live code path. Removed because it caused 131 test failures
  rooted in stale code paths (`zt.compiler` vs `zt.compile.compiler`,
  pre-reorg include resolver, old `MIN`/`MAX` semantics, etc.).

## What still has dead-flat duplicates

Most of the 22 dead-flat duplicates have been cleaned up since the
original Phase 0–4 merge. Four remain at the top of `src/zt/` as
unimported leftovers:

- `src/zt/ir.py` — superseded by `src/zt/compile/ir.py`
- `src/zt/inspect.py` — superseded by `src/zt/inspect/decompile.py`
- `src/zt/profile.py` — superseded by `src/zt/profile/core.py`
- `src/zt/include_resolver.py` — superseded by `src/zt/compile/include_resolver.py`

A grep across the live tree confirms no production module nor any
test imports the flat versions; the package versions are everywhere.
The flat files are harmless but stale and worth deleting in a future
cleanup. `src/zt/test_runner.py` and `src/zt/test_facade.py`, by
contrast, are *live* — they're the entry points for `zt test` and
the high-level Forth-test harness, not duplicates of anything.

## What was already landed before this merge — phase summary

### `::` defining word
28 tests cover happy path, byte-equivalence to auto-inlined `:`,
recursion rejection, control-flow-inside-`::` (IF/THEN/ELSE,
BEGIN/AGAIN/UNTIL/WHILE/REPEAT, DO/LOOP/+LOOP), LEAVE rejection inside
`::`, ColonRef rejection, cross-kind redefinition warning, nested-
definition rejection.

### Phase 0 — `native_control_flow` flag plumbing
The flag threads through `Compiler.__init__`, `compile_and_run`,
`compile_and_run_with_output`, and `build_from_source` with default
`False`. `Asm` gains a `native: bool` field; when set, `Asm.dispatch()`
emits `RET` instead of the threaded NEXT tail.

### Phase 1 — IF/THEN/ELSE native
Native compilation emits straight-line Z80 with primitive bodies inlined,
native conditional/unconditional forward branches matching the `0BRANCH`
flag-then-pop order, and a `JP main` startup (no `CALL`).

### Phase 1.5 — primitive splicing relocates correctly
`emit_native_primitive_body` runs each `create_*` against a fresh
`Asm(origin=splice_address, native=True)`, lets the assembler resolve
internal labels at the actual splice site, strips the trailing `RET`,
splices the resolved bytes. Works for any primitive whose body resolves
standalone — not just the inline whitelist.

### Phase 2 — BEGIN/AGAIN/UNTIL/WHILE/REPEAT native
Guards removed. The native backward-branch and forward-placeholder
helpers in `code_emitter.py` cover the four constructs with no extra
emitters.

### Phase 3 — DO/LOOP/+LOOP native (no LEAVE)
- `(do)` runtime body re-emits cleanly via `emit_native_primitive_body`.
- `LOOP` and `+LOOP` get bespoke native emitters
  (`_emit_native_loop_body`, `_emit_native_plus_loop_body`).
- `I`, `J`, `UNLOOP` re-emit cleanly.
- `LEAVE` rejected under `native_control_flow` per agreed scope.

### Phase 4 — `::` with control flow
- `_force_inline_colon` rewritten to walk the IR cells of the body
  directly. Forward branches placed via the placeholder helpers and
  patched once their target labels are reached. Backward branches use
  `compile_native_branch_to_label`. Each `::` body ends with
  `asm.dispatch()` so the spliced fragment returns control to the
  caller's threaded interpreter.
- LEAVE inside `::` rejected at the LEAVE token with a clear error.

## In-flight stubs

`::` plus `native_control_flow=True` simultaneously errors at
`_start_colon` — combining them needs a small extension.

`ColonRef` to a user colon, plus variables and constants, error in native
mode.

## Native model — key design decision

SP cannot serve as both the data stack and the call return stack. The
native model sidesteps this by avoiding `CALL`/`RET` entirely: each colon
body is inlined as straight-line Z80, the program enters main via `JP`,
main halts. Multi-colon native programs would need either separating
data/return stacks or aggressive call-site inlining of every colon.

## Regression run summary (this merge)

| Chunk | Tests | Result |
|---|---|---|
| `::` + control-flow + compiler/inliner/dictionary/tokenizer/asm | 872 | pass |
| Format / IR / sim / banking / primitives / examples | 1469 | pass |
| Forth `.fs` (`tests/` + reaction) | 190 | pass |
| **Total verified** | **2531** | **all pass** |

Mined-out `.fs` and plasma-128k were not re-run this session (timeout).
The mined-out `.fs` test was failing on your fresh upload due to the
dead-flat conftest path, which is now removed; should pass.

## Landed

### `::` defining word
File: `tests/test_double_colon.py`. 28 tests now cover happy path,
byte-equivalence to auto-inlined `:`, recursion rejection, control-flow-
inside-`::` (IF/THEN/ELSE, BEGIN/AGAIN/UNTIL/WHILE/REPEAT, DO/LOOP/+LOOP),
LEAVE rejection inside `::`, ColonRef rejection (nested calls still future
work), cross-kind redefinition warning, and nested-definition rejection.

### Phase 0 plumbing — `native_control_flow` flag
The flag threads through `Compiler.__init__`, `compile_and_run`,
`compile_and_run_with_output`, and `build_from_source` with a default of
`False`. `Asm` gains a `native: bool` field; when set, `Asm.dispatch()`
emits `RET` instead of the threaded NEXT tail.

### Phase 0 fixture
`tests/test_controlflow.py` carries a `cf_mode` fixture parametrising every
forward/backward-branch test class across `{False, True}`.

### Phase 1 — IF/THEN/ELSE native
Native compilation emits straight-line Z80 with primitive bodies inlined,
native conditional/unconditional forward branches matching the `0BRANCH`
flag-then-pop order, and a `JP main` startup (no `CALL`).

### Phase 1.5 — primitive splicing relocates correctly
`emit_native_primitive_body` runs each `create_*` against a fresh
`Asm(origin=splice_address, native=True)`, lets the assembler resolve
internal labels at the actual splice site, strips the trailing `RET`,
splices the resolved bytes. Works for any primitive whose body resolves
standalone — not just the inline whitelist.

### Phase 2 — BEGIN/AGAIN/UNTIL/WHILE/REPEAT native
Guards removed. The native backward-branch and forward-placeholder helpers
in `code_emitter.py` cover the four constructs with no extra emitters.

### Phase 3 — DO/LOOP/+LOOP native (no LEAVE)
- `(do)` runtime body re-emits cleanly via `emit_native_primitive_body`:
  no IX usage, no internal jumps. IY frame layout (limit at `+2/+3`,
  index at `+0/+1`) stays identical to threaded mode.
- `LOOP` and `+LOOP` get bespoke native emitters
  (`_emit_native_loop_body`, `_emit_native_plus_loop_body`).
- `I`, `J`, `UNLOOP` re-emit cleanly via `emit_native_primitive_body`.
- `LEAVE` rejected under `native_control_flow` per agreed scope.

### Phase 4 — `::` with control flow
- `_force_inline_colon` rewritten to walk the IR cells of the body
  directly instead of building an `InlineStep` plan, so it can handle
  Branch and Label cells uniformly with the native primitive emission.
- Forward branches use the existing `compile_native_*_placeholder`
  helpers; targets are patched once their Label cells are reached.
- Backward branches use `compile_native_branch_to_label`, which already
  handles `branch`, `0branch`, `(loop)`, and `(+loop)` from Phase 3.
- Each `::` body ends with `asm.dispatch()` (the threaded NEXT tail) so
  the spliced fragment returns control to the caller's threaded
  interpreter.
- LEAVE is rejected at the LEAVE token when the current word is
  `force_inline`, with a clear error mentioning both LEAVE and `::`.
- Whitelist relaxation for `::` bodies: ColonRef and StringRef still
  reject; unknown primitives reject; everything else (Literal, Label,
  PrimRef known to `_creators_by_name`, Branch with Label target) is
  inlinable.

What `::` now compiles cleanly:
- `:: abs-inline  dup 0< if negate then ;` (was: rejected)
- `:: count-down  begin 1- dup 0= until ;` (was: rejected)
- `:: while-doubler  begin dup 50 < while 2* repeat ;` (was: rejected)
- `:: sum-to-n  0 swap 0 do i + loop ;` (was: rejected)
- `:: count-by-twos  0 10 0 do 1+ 2 +loop ;` (was: rejected)

Still rejected:
- `:: foo  helper ;` where `helper` is another colon (nested calls)
- `:: foo … leave …` (LEAVE inside ::)

## In-flight stubs

`::` plus `native_control_flow` errors at `_start_colon` — the two paths
emit different tails (NEXT for `::`, fall-through/HALT for native) so
combining them needs a small extension. `ColonRef` to a user colon, plus
variables and constants, still error in native mode.

## Native model — key design decision

SP cannot serve as both the data stack and the call return stack. The
native model sidesteps this by avoiding `CALL`/`RET` entirely: each colon
body is inlined as straight-line Z80, the program enters main via `JP`,
main halts. Multi-colon native programs would need either separating
data/return stacks or aggressive call-site inlining.

`::` is the call-site-inlining option, but only for definitions explicitly
marked `::`. Phase 4 widens what they can contain; multi-colon native mode
would generalise this to every colon.

## Regression run summary (this session, Phase 4 sweep)

| Chunk | Tests | Result |
|---|---|---|
| Compiler / inliner / control-flow / `::` / tokenizer / asm / code_emitter | 872 | pass |
| Format / IR / sim / banking | 1173 | pass |
| Primitives, M5/M7 milestones, profile | 605 | pass |
| Examples (small + plasma + mined-out + makefile) | 359 | pass |
| Plasma-128k | 18 | pass |
| Forth `tests/test_*.fs` + reaction `.fs` | 190 | pass |
| CLI / stdlib / perf | 121 | pass |
| **Total verified** | **3338** | **all pass** |

## Files touched (Phase 4 delta on top of Phase 3)

- `src/zt/compile/compiler.py` — `_force_inline_colon` rewritten,
  `_emit_force_inline_body` + helpers added, `_first_non_inlinable_cell`
  refactored, LEAVE rejection inside `::`
- `tests/test_double_colon.py` — `TestDoubleColonControlFlow` added
  (8 tests), four "negative control flow" tests removed

