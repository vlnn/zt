# Assembler words (`:::`) and the macro layer

Most of the time you write Forth in `:` or `::`. Sometimes you need a
primitive — a single dispatch's worth of Z80 — that doesn't exist yet. The
`:::` directive lets you write one in raw assembly without leaving your
source file or touching `primitives.py`.

```forth
::: name ( stack-effect )
    asm-mnemonic asm-mnemonic ... ;
```

Every token between the name and `;` is one of three things: an asm
mnemonic, a numeric literal (consumed as an immediate operand), or a
parse-time macro that rewrites the token stream. The closing `;` adds the
threaded-interpreter dispatch tail; everything else is yours.

## Calling convention

`:::` runs in the same VM as `primitives.py`. The contract is:

| Register | Role | Touch? |
|----------|------|--------|
| `HL` | TOS | Yes — but you reload it on entry/exit yourself |
| `IX` | Threaded instruction pointer | No |
| `IY` | Return-stack pointer | No |
| `SP` | Parameter-stack pointer | Read-only via `push`/`pop` |
| `A`, `B`, `C`, `D`, `E` | Scratch | Yes |
| Shadow registers | Not modelled | Don't use |

In practice that means: read TOS from `HL`, do your work in `A`/`BC`/`DE`,
write the new TOS back to `HL` (or pop the old one if you consumed it),
then `;` emits the dispatch tail. If you need `HL` itself as a working
pointer, the cheapest park is `ex de,hl` — one byte, reversible. Worry
about `IX`/`IY` only if you're writing something that genuinely belongs in
`primitives.py` instead.

There is no automatic prologue or epilogue. If your stack effect is
`( x -- )` you must `pop_hl` before `;`. If it's `( -- y )` you must
`push_hl` before loading the new TOS into `HL`. The compiler doesn't read
your stack-effect comment; it's documentation for the reader, not a
contract.

## The vocabulary inside `:::`

Three categories of token are recognised:

**Asm mnemonics.** Every entry from `OPCODES` is exposed by its method
name: `ld_a_l`, `ld_hl_nn`, `inc_hl`, `ex_de_hl`, `pop_hl`, and so on. If
the operand kind is `n` or `nn`, the immediate sits on the host stack at
compile time, postfix — `3000 ld_hl_nn` means "push 3000 to host stack,
then `ld_hl_nn` pops it and emits `LD HL, 3000`."

**Pseudo-mnemonics.** Things that aren't real opcodes but emit bytes:

- `byte` — `( n -- )` host-stack pop, emits one raw byte.
- `word` — `( n -- )` host-stack pop, emits two raw bytes (little-endian).
- `label name` — declares a local label at the current address. Scoped
  to this `:::` body; the same name in another `:::` is a different
  label.
- `jp`, `jp_z`, `jp_nz`, `jp_p`, `jp_m`, `call` — 3-byte absolute jumps
  that take a target name. The name is resolved as: declared local label
  first, then global word, then deferred local (forward reference).
- `jr`, `jr_z`, `jr_nz`, `jr_c`, `jr_nc`, `djnz` — 2-byte relative jumps,
  same name resolution. Range is ±128 bytes; falls out of fixup if your
  target is too far.

**Numeric literals.** Push to the host stack at compile time. Mnemonics
that take operands pop them.

## Macros — `[name]`

Macros are parse-time token rewriters. They run before the compiler's
state machine sees them, so they work in interpret state, in `:` and `::`
colon bodies, and inside `:::`. They're the right home for compile-time
control that doesn't belong in any one of those layers.

| Macro | What it does |
|-------|--------------|
| `[TIMES] N TOK` | Splice `N` copies of the next token into the stream. |
| `[DEFINED] name` | Push 1 to host stack if `name` is a defined word, 0 otherwise. |
| `[IF] / [ELSE] / [THEN]` | Pop host stack; truthy keeps the `[IF]` branch, falsy keeps the `[ELSE]` branch. Nest with proper depth tracking. |
| `[string] s" body"` | Emit each byte of `body` inline at the current code address (interpret state only). Useful inside `create` blocks. |
| `'` (tick) | Read next token as a name, push its address to host stack. |
| `[']` (bracket-tick) | Inside a colon body, compile a runtime literal of the next word's address. |

## Examples

```forth
( Add 2 to TOS — useful for advancing pointers across cells. )
::: cell+ ( addr -- addr+2 )
    inc_hl inc_hl ;

( If TOS is non-zero, leave a copy on the stack. Forward-references a
  local label, declared just before `;`. )
::: ?dup ( n -- 0 | n n )
    ld_a_l or_h
    jr_z skip
    push_hl
    label skip ;

( Increment the byte at TOS-as-address, then drop the address. )
::: 1c+! ( addr -- )
    inc_ind_hl
    pop_hl ;
```

The full set of working examples lives in `examples/asm-primitives/asm-primitives.fs`,
and `tests/test_examples_asm_primitives.py` runs each one through the
simulator. Treat that pair as the executable spec — if you change the
examples, run the tests.

## Block operations: `LDIR` and the seed-and-propagate trick

Z80's `LDIR` instruction is a hardware loop:

```
repeat:
    LD (DE), (HL)     ; copy one byte
    INC HL            ; advance source
    INC DE            ; advance destination
    DEC BC            ; one fewer to go
    jump-if-nonzero repeat
```

It runs strictly byte-by-byte, re-reading `(HL)` on every iteration. Two
consequences worth knowing.

**As a memcpy.** If source and destination don't overlap (or the
destination is *behind* the source), `LDIR` is the fastest way to copy
a region — 21 T-states per byte versus ~80 for a Forth `c@ c! 1+ 1+`
loop. Set `HL = src`, `DE = dst`, `BC = count`, and emit `ldir`.

**As a fill, via overlap.** If `DE = HL + 1`, every iteration reads the
byte the previous iteration just wrote. So `LDIR` from 4000 to 4001 with
`BC = 300` doesn't copy 300 bytes — it propagates the single byte at
4000 across 4001 through 4300. This is the seed-and-propagate fill: plant
one byte at the start, point `HL` at it and `DE` one ahead, and `LDIR`
fans the seed across the whole region. The `fill-byte` example in
`examples/asm-primitives/asm-primitives.fs` does exactly this.

**`BC == 0` means 65536.** `LDIR` decrements first, tests after. So a
zero count overwrites a quarter of the address space. Always guard with
something like:

```
ld_a_b or_c           ( flags = BC == 0 ? )
jr_z done             ( skip the LDIR if so )
```

This trap is the one place where `:::` is genuinely more demanding than
`:`: a Forth `do` loop with count 0 just doesn't iterate, but `LDIR`
needs an explicit early-out.

**The classic gotcha.** People reach for `LDIR` as a memcpy on
*forward-overlapping* regions (e.g., shifting a buffer one byte right)
and get a single byte broadcast across the destination instead of the
buffer they expected. The fix is to either copy backwards (which would
need `LDDR` — not currently in OPCODES) or to copy via a temporary
buffer.

## When to reach for `:::`, when to write Python

`:::` is a slice of `primitives.py`. It's the right tool when the body is
straight-line or simple-branched assembly that respects the calling
convention. It's not the right tool when:

- you need to manipulate `IX`/`IY` (write a primitive in Python instead);
- you need cross-`:::` labels (the scoping is intentional — define the
  destination as its own `:::` and call it by name);
- you need helpers shared between primitives (those go in
  `primitives.py` as `_emit_foo` functions);
- the body is large and would benefit from the inliner's optimisation.

A good heuristic: if you'd write the same thing in `primitives.py` as
five lines and three `Asm` method calls, it belongs in `:::`. If it's
twenty lines with helpers, put it in `primitives.py`.

## ISRs: prefer `:` over `:::`

For IM 2 handlers, write a normal `:` colon word and install it with
`IM2-HANDLER! ( xt -- )`. The shim emitted by `IM2-HANDLER!` saves
AF/HL/BC/DE/IX/IY on entry and ends with `EI; RETI` on exit, so the
body is plain Forth — no `push_af … pop_af`, no manual `ei reti`, no
register bookkeeping.

```forth
variable border-tick

: rainbow-isr  ( -- )
    border-tick @ 1+ 7 and  dup border-tick !  border ;

: main  ['] rainbow-isr im2-handler!  ei  begin again ;
```

The body must be stack-neutral on both stacks. The shim doesn't swap to
a private SP, so `>R` without a matching `R>` (or pushing a literal
without consuming it) leaks into the foreground.

Use `:::` for an ISR only when the per-fire budget genuinely demands
the ~140-T-state shim be skipped — tracker drivers, raster splits.
You're then on the hook for `push af … pop af … ei reti` yourself, and
you install by writing `$B9BA` directly instead of through
`IM2-HANDLER!` (which would route through the shim).
