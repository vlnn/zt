# Forth primitives reference

Runtime primitives compiled into every `zt` image, organized by capability.

Stack effects use the conventional Forth notation `( before -- after )`,
with the rightmost cell being the top of stack (TOS). All values are
16-bit signed unless marked `u` (unsigned). Truth values follow Forth
convention: `0` is false, comparisons return `-1` (all bits set) for
true.

The canonical user-facing names use Forth-style symbols (`@`, `!`, `0=`,
`u/mod`, `bank!`); each primitive is also registered under an underscore
alias (e.g. `fetch`, `store`, `zero_equals`, `u_mod_div`, `bank_store`)
so the dictionary stays grep-friendly. Either form compiles.

For implementation, see [`src/zt/assemble/primitives.py`](../src/zt/assemble/primitives.py).
For milestone history of how these landed, see [`PLAN.md`](PLAN.md).

---

## Quick reference

| Category    | Words                                                                |
|-------------|----------------------------------------------------------------------|
| Stack       | `dup` `drop` `swap` `over` `rot` `nip` `tuck` `2dup` `2drop` `2swap` |
| Return      | `>r` `r>` `r@`                                                       |
| Arithmetic  | `+` `-` `1+` `1-` `2*` `2/` `*` `u/mod` `negate` `abs` `min` `max`   |
| Logic       | `and` `or` `xor` `invert` `lshift` `rshift`                          |
| Comparison  | `=` `<>` `<` `>` `0=` `0<` `u<`                                      |
| Memory      | `@` `!` `c@` `c!` `+!` `dup@` `cmove` `fill`                         |
| Storage     | `,` `c,` `allot`                                                     |
| Text I/O    | `emit` `key` `key?` `key-state` `type` `at-xy` `reset-cursor` `scroll-attr` |
| Hardware    | `border` `beep` `wait-frame` `halt`                                  |
| 128K banks  | `bank@` `bank!` `raw-bank!` `128k?`                                  |
| Internal    | `lit` `branch` `0branch` `(do)` `(loop)` `(+loop)` `i` `j` `unloop` `next` `docol` `exit` |

Signed `/`, `/mod`, `mod` are not primitives; they live in
[`stdlib/core.fs`](../src/zt/stdlib/core.fs) on top of `u/mod`.

---

## Stack operations

### `dup` `( n -- n n )`
Duplicate TOS.

### `drop` `( n -- )`
Discard TOS.

### `swap` `( a b -- b a )`
Exchange the top two cells.

### `over` `( a b -- a b a )`
Copy the second cell to the top.

### `rot` `( a b c -- b c a )`
Rotate the top three cells so the third becomes TOS.

### `nip` `( a b -- b )`
Drop the second cell.

### `tuck` `( a b -- b a b )`
Copy TOS underneath the second cell.

### `2dup` `( a b -- a b a b )`
Duplicate the top pair.

### `2drop` `( a b -- )`
Discard the top pair.

### `2swap` `( a b c d -- c d a b )`
Swap the top two pairs.

---

## Return stack

### `>r` `( n -- )` `R:( -- n )`
Move TOS onto the return stack.

### `r>` `( -- n )` `R:( n -- )`
Move the top of the return stack onto the data stack.

### `r@` `( -- n )` `R:( n -- n )`
Copy the top of the return stack onto the data stack.

```forth
: over-via-rstack  ( a b -- a b a )  >r dup r> swap ;
```

---

## Arithmetic

### `+` `( a b -- a+b )`
Signed 16-bit addition.

### `-` `( a b -- a-b )`
Signed 16-bit subtraction.

### `1+` `( n -- n+1 )` and `1-` `( n -- n-1 )`
Increment / decrement.

### `2*` `( n -- n*2 )` and `2/` `( n -- n/2 )`
Arithmetic left/right shift by one. `2/` is sign-preserving.

### `*` `( a b -- a*b )`
Signed 16-bit multiplication. Result wraps modulo 2¹⁶.

### `u/mod` `( u_dividend u_divisor -- u_remainder u_quotient )`
Unsigned 16-bit division. Signed `/`, `/mod`, `mod` are defined in
`stdlib/core.fs` on top of this.

### `negate` `( n -- -n )`
Two's-complement negation.

### `abs` `( n -- |n| )`
Absolute value.

### `min` `( a b -- min )` and `max` `( a b -- max )`
Signed minimum / maximum.

---

## Logic and shifts

### `and`, `or`, `xor` `( a b -- a∘b )`
Bitwise AND / OR / XOR.

### `invert` `( n -- ~n )`
Bitwise complement. `0 invert` is `-1`.

### `lshift` `( n u -- n<<u )` and `rshift` `( n u -- n>>u )`
Logical left / right shift by `u` bits. `rshift` zero-fills (use `2/`
for sign-preserving arithmetic right shift by 1).

---

## Comparison

All comparisons leave `-1` for true, `0` for false.

### `=`, `<>` `( a b -- flag )`
Equality / inequality.

### `<`, `>` `( a b -- flag )`
Signed less-than / greater-than.

### `0=`, `0<` `( n -- flag )`
True when `n` is zero / negative. `0=` doubles as logical NOT.

### `u<` `( a b -- flag )`
Unsigned less-than. Useful for address comparisons; `1 -1 u<` is true
because `-1` is `$FFFF` unsigned.

---

## Memory

### `@` `( addr -- n )` and `!` `( n addr -- )`
16-bit cell fetch / store.

### `c@` `( addr -- b )` and `c!` `( b addr -- )`
Byte fetch (zero-extended to a cell) / byte store (low byte of `b`).

### `+!` `( n addr -- )`
Add `n` to the cell at `addr`.

### `dup@` `( addr -- addr n )`
Fused `dup @`. Saves one dispatch in tight `addr addr @` patterns.

### `cmove` `( src dst count -- )`
Copy `count` bytes from `src` to `dst`, low addresses first.

### `fill` `( addr count byte -- )`
Fill `count` bytes starting at `addr` with `byte`.

```forth
22528 768 56 fill   \ paint the whole attribute area white-on-black
```

---

## Compile-time storage

These primitives are typically used inside word definitions to lay down
data alongside code.

### `,` `( n -- )`
Append a 16-bit cell to the current definition.

### `c,` `( b -- )`
Append a single byte to the current definition.

### `allot` `( n -- )`
Reserve `n` bytes after `here`. Used by `variable` and `create` to
allocate data space.

---

## Text I/O

### `emit` `( c -- )`
Print one character at the current cursor position. Routes through the
ROM font; the cursor advances and wraps.

### `key` `( -- c )`
Block until a key is pressed; return its ASCII code.

### `key?` `( -- flag )`
Non-blocking poll; return `-1` if any key is currently down, `0`
otherwise.

### `key-state` `( -- bitmap )`
Snapshot of the keyboard matrix as a 16-bit bitmap. See
`stdlib/input.fs` for higher-level helpers.

### `type` `( addr count -- )`
Print `count` bytes starting at `addr`. Pairs with `s"`-produced
string literals.

### `at-xy` `( col row -- )`
Move the text cursor. Coordinates are character cells (0–31 columns,
0–23 rows on a 48K screen).

### `reset-cursor` `( -- )`
Move the cursor to the top-left and clear the underlying tracking
state.

### `scroll-attr` `( -- )`
Scroll the attribute area up by one row. Used by line-mode text
output when the cursor falls off the bottom.

---

## Spectrum hardware

### `border` `( n -- )`
Set the border colour (0–7); writes to port `$FE`.

```forth
2 border             \ red
: flash  0 begin dup border 1+ again ;
```

### `beep` `( cycles period -- )`
Square-wave tone on port `$FE` bit 4 (the ROM beeper line). `cycles`
is the number of half-period iterations; `period` is the half-period
in T-states. See `stdlib/sound.fs` for `click`, `chirp`, `low-beep`,
`high-beep`, `tone`.

### `wait-frame` `( -- )`
Block until the next 50 Hz frame interrupt fires. Foundation for
frame-paced animation and timing.

### `halt` `( -- )`
Execute Z80 `HALT`. Ends the program when no interrupt handler is
installed (common case); useful both as a clean program terminator
and as the stop signal `zt test` watches for.

---

## 128K banking

These primitives only behave as documented on a 128K target; on a 48K
target `128k?` returns false and the others are unsafe. See
[`128k-architecture.md`](128k-architecture.md) for the full model.

### `128k?` `( -- flag )`
Runtime detection. Returns `-1` on a Spectrum 128 (or compatible),
`0` otherwise.

### `bank@` `( addr bank -- n )`
Fetch a cell from `addr` (which must be in the `$C000–$FFFF` window)
in RAM bank `bank` (0–7). Switches the page in, reads, switches back.

### `bank!` `( n addr bank -- )`
Store a cell to `addr` in RAM bank `bank`. Page-in / store / page-out.

### `raw-bank!` `( bank -- )`
Low-level: write `bank` directly to port `$7FFD`. Caller is responsible
for restoring page 0 if needed; prefer `bank@`/`bank!` unless you know
why you need the raw form.

---

## Internal (compiled only)

These are emitted by the compiler; they are never written by hand in
source.

### `lit` `( -- n )`
Push the inline 16-bit cell that follows the `lit` address in the
threaded stream. Compiled automatically when a number appears in a
definition.

### `branch` `( -- )`
Unconditional jump; the next cell is the branch target. Compiled by
`begin`/`again` and `else`.

### `0branch` `( flag -- )`
Conditional jump taken when `flag` is zero. Compiled by `if`,
`while`, `until`.

### `(do)` `( limit start -- )` `R:( -- limit start )`
Counted-loop entry. Compiled by `do`. Pushes the limit and current
index onto the return stack.

### `(loop)` `( -- )` `R:( limit i -- limit i+1 | )`
Counted-loop step. Compiled by `loop`. Increments the index, branches
back to the matching `(do)` if the index has not reached the limit.

### `(+loop)` `( n -- )` `R:( limit i -- limit i+n | )`
Counted-loop step with explicit increment. Compiled by `+loop`.

### `i` `( -- index )` and `j` `( -- index )`
Read the innermost / next-outer counted-loop index off the return
stack. Compiled inside `do`/`loop` bodies.

### `unloop` `( -- )` `R:( limit i -- )`
Discard the current loop frame from the return stack. Compiled before
`exit` inside a `do`/`loop` body, or as part of `leave`.

### `next` `(internal)`
The dispatch sequence at the heart of the indirect-threaded VM.
Implemented inline at the end of every other primitive.

### `docol` `(internal)`
Colon-word entry trampoline: pushes the caller's IP, walks the body.

### `exit` `R:( addr -- )`
Return from the current colon definition. Compiled automatically by
`;`.
