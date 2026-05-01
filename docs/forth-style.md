# Forth style and best practices

How to write Forth that's easy to read, easy to test, and stays within
the grain of the system. The advice below is opinionated and specific to
this codebase; orthodox Forth tradition will agree with most of it.

## The shape of a Forth program

Forth is fractal. A program is words built from words built from words,
all the way down to primitives. The single most important habit:
**factor aggressively, name clearly, write small words.**

```forth
\ bad: one fat word that buries the meaning in stack juggling
: paint-row  ( row -- )
    32 0 do
        i over swap dup empty? if 32 else 35 then swap at-xy emit
    loop drop ;

\ good: each word does one thing, the names tell you what
: tile-glyph     ( col row -- char )  empty? if 32 else 35 then ;
: paint-cell     ( col row -- )       2dup at-xy tile-glyph emit ;
: paint-row      ( row -- )           32 0 do i over paint-cell loop drop ;
```

Three lines instead of one, and you can read each in isolation, test
each in isolation, and recombine them in surprising ways without
duplicating logic. **A four-line word body is plenty.** If you need
more, you've found a missing word; name it and split.

## Naming conventions

Forth's name vocabulary is ASCII-rich because the alphabet is too
narrow for a stack language. Pattern-match on suffix:

| Suffix    | Reads as           | Stack hint                |
|-----------|--------------------|---------------------------|
| `?`       | "is a ...?"        | `( ... -- flag )`         |
| `@`       | "fetch"            | `( addr -- value )`       |
| `!`       | "store"            | `( value addr -- )`       |
| `+!`      | "add to"           | `( n addr -- )`           |
| `c@` / `c!` | "byte fetch/store" | `( addr -- byte )` etc. |
| `>foo`    | "convert to foo"   | `( other -- foo )`        |
| `foo>`    | "convert from foo" | `( foo -- other )`        |
| `(foo)`   | "internal form of foo" | usually a runtime helper not meant to be called directly |
| `-foo`    | "negative ..." or "without ..." | depends on context |

Examples from the stdlib: `empty?` is a predicate, `tile@` fetches a
tile, `tile!` stores one, `+!` adds to a cell, `>r` moves to the return
stack. Lean on these — readers expect them.

For names that aren't single words, use `-` as the separator:
`paint-row`, `tile-glyph`, `board-cols`, `start-col`. Lower-case is the
default; tokenizer folds case anyway, but lower-case is friendlier.

## Stack effects: write them, read them as types

Every word should carry a stack effect comment. They're not optional —
they're how you read Forth code without holding it in your head.

```forth
: tile-glyph  ( col row -- char )  empty? if 32 else 35 then ;
```

Read left-to-right: takes `col` and `row` (with `row` on top of stack),
leaves `char`. Treat the `--` as "becomes." The names matter — `( a b
-- c d )` is much weaker than `( col row -- char glyph )`. Pick names
that say what the value *means*, not just its type.

A stack effect comment is the one place you should write words that
aren't executable. Don't comment the body — make the body
self-explanatory.

```forth
\ avoid: redundant prose, body already says this
: paint-cell ( col row -- )
    2dup at-xy        \ position cursor at col, row
    tile-glyph        \ get the glyph for that tile
    emit ;            \ write it out

\ better: stack effect plus the body, no narration
: paint-cell ( col row -- )
    2dup at-xy  tile-glyph  emit ;
```

If the body needs prose to be readable, the body needs more factoring.

## Choosing the definition form

Three choices, in order of how often you should reach for each:

**`:` — regular colon definition.** The default. Compiles into a threaded
sequence of cell-sized references; runtime walks them. Fast enough for
99% of work. Use this unless you have a specific reason not to.

**`::` — force-inline colon.** Same as `:` but the inliner attempts to
splat the body's primitives directly into the caller, eliminating the
dispatch overhead. Worth reaching for in inner loops where each
primitive's NEXT cost is measurable, **not for cleanliness or
correctness**. Inlined bodies grow each caller's size, so `::` on a word
called from many places multiplies image size.

```forth
\ ok: hot inner loop, body is all-primitive so the inliner can splat it
:: 2*+1   ( n -- 2n+1 )   dup + 1+ ;

\ overkill: called from a dozen places, makes the image bigger for
\ no real win
:: ch-space   ( -- ch )   32 ;
```

A body that references variables, colon words, or any non-primitive
won't actually inline — the compiler errors. `::` is specifically a tool
for primitive-heavy leaf words.

A good heuristic: if you'd profile-and-tune in Python before reaching
for C, the analogue here is "profile-and-tune in `:` before reaching
for `::`."

**`:::` — assembler word.** When the body is short straight-line Z80
that doesn't have a clean Forth expression. See `docs/asm-words.md` for
the full story; the short version is "use this for one or two-line
primitives that the existing vocabulary makes awkward." Most code never
needs this.

```forth
\ a primitive that genuinely belongs in :::
::: cell+  ( addr -- addr+2 )   inc_hl inc_hl ;
```

If the body would be more than ~10 instructions, it probably belongs in
`primitives.py` instead — that file has helpers for shared subroutines,
better debugging support, and isn't constrained to the calling
convention `:::` enforces.

## Testing

Forth-side tests live in `tests/*.fs`, run by the Python harness in
`tests/forth_runner.py`. The library at `stdlib/test-lib.fs` provides
`assert-eq`, `assert-true`, `assert-false`. Each test is a word starting
with `test-` that the harness calls and checks `_result`.

```forth
include test-lib.fs

: test-cell+        100 cell+   102 assert-eq ;
: test-cell-zero    0   cell+   2   assert-eq ;
: test-cell-wraps   65535 cell+ 1   assert-eq ;
```

A few habits that pay off:

**One concept per test.** Each `test-foo` should pin one observable
behaviour. If you have to write `assert-eq` twice in the same test,
you're testing two things — split.

**Parametrize via separate tests, not via loops.** Forth doesn't have
pytest's `parametrize`. Just write each case as its own `test-foo-bar`.
The names document the case.

**Test the contract, not the implementation.** A test that breaks when
you refactor the body is a bad test. A test that breaks when the stack
effect changes is a good test.

For Python-side tests of compiled-and-run behaviour (rare — usually
you only need this when the test crosses into the Z80 simulator), use
`compile_and_run` from `zt.compile.compiler`. See
`tests/test_examples_asm_primitives.py` for the pattern.

## Inline assembly: when, why, how

`:::` is sometimes the right tool. It's almost never the *first* tool.

**When it's right:**

- The Forth expression of the operation is genuinely awkward and would
  require multiple primitives where the asm needs one or two.
- You need a primitive that doesn't exist in `primitives.py` and the
  body is short.
- You're emitting bytes inline (`[string]`, lookup tables, sprite
  data) where Forth doesn't have a syntax.

**When it's not right:**

- Speed in the abstract — measure before optimizing. `::` often beats
  `:::` because the inliner does the obvious work for free.
- "I want raw control over registers" — you usually don't, and the
  calling convention will surprise you.
- Anything that needs `IX` or `IY` — that's a `primitives.py` job.

**The rule of thumb: a `:::` word should be one screen short, and a
reader unfamiliar with Z80 should be able to skip it without losing
the program's flow.** If `:::` is appearing in the middle of your
algorithm, factor the algorithm so the `:::` part is a clearly named
leaf.

```forth
\ good: :::  is a small, well-named leaf
::: 1c+!  ( addr -- )   inc_ind_hl pop_hl ;

: tally-bucket  ( bucket-base index -- )  + 1c+! ;

: tally  ( n -- )
    bucket-of buckets-base swap tally-bucket ;
```

The asm is invisible to the rest of the program. That's the goal.

## Common pitfalls

**Postfix immediates inside `:::`.** Numbers go to the host stack at
compile time; mnemonics with operands pop them. So `3000 ld_hl_nn`,
not `ld_hl_nn 3000`.

**Forth comments don't nest.** `( ... ( foo ) ... )` ends at the first
`)`, leaving the rest as parser input. Either avoid `(` inside
comments, or use `\` line comments instead.

**`::`is not free.** Each call site grows. Use it in inner loops, not
on every short word.

**Magic numbers are a smell.** If `32` appears five times in your
file, name it. The stdlib does this with `constant`:

```forth
32 constant ch-space
35 constant ch-fence
0  constant t-empty
```

Reading `t-empty grid-clear` is much better than `0 grid-clear`.

**Stack juggling beyond `swap rot over` suggests a missing word.** If
you find yourself writing `>r dup r> swap` and friends to wrangle a
data flow, the function probably wants different parameters. Add a
small helper word that hides the juggle, or rethink the API.

**Forward references inside `:::`.** Local labels defined later in the
body work, but if a global word happens to share the name, the global
wins for forward references. Pick label names like `top`, `done`,
`skip` that are unlikely to clash.

## A quick worked example

Suppose you want a word `fill-byte` that fills `count` bytes starting
at `addr` with `byte-value`. Step through how each layer might handle
it.

**Naive `:` version:** loops in Forth, fine for small counts.

```forth
: fill-byte  ( addr count byte -- )
    rot rot 0 do                              ( byte addr )
        2dup c! 1+                            ( byte addr+1 )
    loop 2drop ;
```

Readable but slow — every byte costs one `c!` plus loop overhead.

**`::` version:** same body, force-inlined into callers. Cuts dispatch
cost. Same algorithm.

```forth
:: fill-byte  ( addr count byte -- )
    rot rot 0 do  2dup c! 1+  loop 2drop ;
```

**`:::` version:** Z80's `LDIR` block-move instruction repeats `LD (DE),
(HL); INC HL; INC DE; DEC BC` until `BC == 0` — strictly byte-by-byte,
re-reading from `(HL)` each iteration. That last detail is the trick:
when the source and destination *overlap with destination one ahead of
source*, `LDIR` reads the byte just written through its previous
iteration. So `LDIR` from 4000 to 4001 with `BC = 300` doesn't copy a
buffer — it propagates the single byte at 4000 across 4001-4300. We
exploit that to fill: seed one byte, then point `HL` at the seed and
`DE` one ahead, and `LDIR` fans the seed out across the whole region.

In any other context this overlap behaviour is the classic LDIR
gotcha — people reach for it as a memcpy and get garbage when their
regions touch. Here, it's the mechanism.

```forth
::: fill-byte  ( addr count byte -- )
    pop_bc                          ( BC = count )
    pop_de                          ( DE = addr )
    ld_a_b or_c                     ( flags = BC == 0 ? )
    jr_z done                       ( if count == 0, do nothing )
    ld_a_l                          ( A = byte )
    ld_ind_de_a                     ( plant seed at addr )
    dec_bc
    ld_a_b or_c
    jr_z done                       ( if count == 1, no propagation )
    ld_h_d ld_l_e                   ( HL = addr — read from seed )
    inc_de                          ( DE = addr+1 — write one ahead )
    ldir                            ( fan seed across the rest )
    label done
    pop_hl ;                        ( drop original byte; new TOS )
```

The boundary cases (`count == 0`, `count == 1`) need explicit guards
because `LDIR` with `BC == 0` would interpret it as 65536 — exactly
the kind of subtle thing that makes `:::` more demanding than `:`.

The point isn't that any of these is universally right. It's that you
pick based on profiling: is `fill-byte` even hot? Most of the time the
plain `:` version is fine; the `::` form gives you a free 2× when it
matters; the `:::` form is for the cases where neither is enough.

**Default to `:`. Reach for `::` when you measure. Reach for `:::`
when measurement isn't enough.**

## Reading list inside this codebase

- `stdlib/core.fs` — short, idiomatic Forth; read this first.
- `stdlib/test-lib.fs` — assertion vocabulary.
- `examples/mined-out/app/board.fs` — well-factored small words with
  stack effects throughout.
- `docs/asm-words.md` — the `:::` reference and macro layer.
- `examples/asm-primitives.fs` — `:::` examples that compile and run.
