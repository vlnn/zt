# Forth Primitives Reference

Runtime primitives currently compiled into every `zt` image, based on the
milestones marked complete in `PLAN.md` (M0, M1, M1.5, M2, M3).

Stack effects use the conventional Forth notation `( before -- after )`, with
the rightmost cell being the top of stack (TOS). All values are 16-bit signed
unless noted. `U<` is the only unsigned comparison in this list.

> Status note: `*`, `/`, `/MOD`, `MOD` (M1.25) and control-flow runtime words
> `(DO)`, `(LOOP)`, `I`, `J`, `0BRANCH` (M4) are not yet part of this set.
> EMIT/KEY/TYPE (M5) are also out of scope here.

---

## Quick reference

| Category    | Words                                                          |
|-------------|----------------------------------------------------------------|
| Stack       | `DUP` `DROP` `SWAP` `OVER` `ROT` `NIP` `TUCK` `2DUP` `2DROP` `2SWAP` |
| Return      | `>R` `R>` `R@`                                                 |
| Arithmetic  | `+` `-` `1+` `1-` `2*` `2/` `NEGATE` `ABS` `MIN` `MAX`         |
| Logic       | `AND` `OR` `XOR` `INVERT` `LSHIFT` `RSHIFT`                    |
| Comparison  | `=` `<>` `<` `>` `0=` `0<` `U<`                                |
| Memory      | `@` `!` `C@` `C!` `+!` `CMOVE` `FILL`                          |
| Spectrum    | `BORDER`                                                       |
| Internal    | `LIT` `BRANCH` `EXIT`                                          |

Truth values follow Forth convention: `0` is false, any non-zero is true.
Comparisons return `-1` (all bits set) for true and `0` for false.

---

## Stack operations

### `DUP` `( n -- n n )`
Duplicate TOS.

```forth
5 dup
```
Leaves `5 5`.

### `DROP` `( n -- )`
Discard TOS.

```forth
5 7 drop
```
Leaves `5`.

### `SWAP` `( a b -- b a )`
Exchange the top two cells.

```forth
1 2 swap
```
Leaves `2 1`.

### `OVER` `( a b -- a b a )`
Copy the second cell to the top.

```forth
1 2 over
```
Leaves `1 2 1`.

### `ROT` `( a b c -- b c a )`
Rotate the top three cells so the third becomes TOS.

```forth
1 2 3 rot
```
Leaves `2 3 1`.

### `NIP` `( a b -- b )`
Drop the second cell.

```forth
1 2 nip
```
Leaves `2`.

### `TUCK` `( a b -- b a b )`
Copy TOS underneath the second cell.

```forth
1 2 tuck
```
Leaves `2 1 2`.

### `2DUP` `( a b -- a b a b )`
Duplicate the top pair.

```forth
1 2 2dup
```
Leaves `1 2 1 2`.

### `2DROP` `( a b -- )`
Discard the top pair.

```forth
1 2 3 4 2drop
```
Leaves `1 2`.

### `2SWAP` `( a b c d -- c d a b )`
Swap the top two pairs.

```forth
1 2 3 4 2swap
```
Leaves `3 4 1 2`.

---

## Return stack

### `>R` `( n -- )` `R:( -- n )`
Move TOS onto the return stack.

### `R>` `( -- n )` `R:( n -- )`
Move the top of the return stack onto the data stack.

### `R@` `( -- n )` `R:( n -- n )`
Copy the top of the return stack onto the data stack.

```forth
: over-via-rstack  ( a b -- a b a )  >r dup r> swap ;
```

---

## Arithmetic

### `+` `( a b -- a+b )`
Signed 16-bit addition.

```forth
3 4 +
```
Leaves `7`.

### `-` `( a b -- a-b )`
Signed 16-bit subtraction.

```forth
10 3 -
```
Leaves `7`.

### `1+` `( n -- n+1 )`
Increment.

```forth
41 1+
```
Leaves `42`.

### `1-` `( n -- n-1 )`
Decrement.

```forth
43 1-
```
Leaves `42`.

### `2*` `( n -- n*2 )`
Arithmetic left shift by one (signed multiply by 2).

```forth
21 2*
```
Leaves `42`.

### `2/` `( n -- n/2 )`
Arithmetic right shift by one (signed divide by 2, sign-preserving).

```forth
84 2/
```
Leaves `42`.

### `NEGATE` `( n -- -n )`
Two's-complement negation.

```forth
5 negate
```
Leaves `-5`.

### `ABS` `( n -- |n| )`
Absolute value.

```forth
-7 abs
```
Leaves `7`.

### `MIN` `( a b -- min )`
Signed minimum.

```forth
3 7 min
```
Leaves `3`.

### `MAX` `( a b -- max )`
Signed maximum.

```forth
3 7 max
```
Leaves `7`.

---

## Logic and shifts

### `AND` `( a b -- a&b )`
Bitwise AND.

```forth
$FF $0F and
```
Leaves `$0F`.

### `OR` `( a b -- a|b )`
Bitwise OR.

```forth
$F0 $0F or
```
Leaves `$FF`.

### `XOR` `( a b -- a^b )`
Bitwise XOR.

```forth
$FF $0F xor
```
Leaves `$F0`.

### `INVERT` `( n -- ~n )`
Bitwise complement.

```forth
0 invert
```
Leaves `-1` (`$FFFF`).

### `LSHIFT` `( n u -- n<<u )`
Logical left shift by `u` bits.

```forth
1 3 lshift
```
Leaves `8`.

### `RSHIFT` `( n u -- n>>u )`
Logical right shift by `u` bits (zero-fill).

```forth
$80 3 rshift
```
Leaves `$10`.

---

## Comparison

All comparisons leave `-1` for true, `0` for false.

### `=` `( a b -- flag )`
Equality.

```forth
5 5 =
```
Leaves `-1`.

### `<>` `( a b -- flag )`
Inequality.

```forth
5 6 <>
```
Leaves `-1`.

### `<` `( a b -- flag )`
Signed less-than.

```forth
3 7 <
```
Leaves `-1`.

### `>` `( a b -- flag )`
Signed greater-than.

```forth
7 3 >
```
Leaves `-1`.

### `0=` `( n -- flag )`
True when `n` is zero; doubles as logical NOT.

```forth
0 0=
```
Leaves `-1`.

### `0<` `( n -- flag )`
True when `n` is negative.

```forth
-1 0<
```
Leaves `-1`.

### `U<` `( a b -- flag )`
Unsigned less-than.

```forth
1 -1 u<
```
Leaves `-1` (because `-1` is `$FFFF` unsigned).

---

## Memory

### `@` `( addr -- n )`
Fetch a 16-bit cell from `addr`.

```forth
variable x   42 x !   x @
```
Leaves `42`.

### `!` `( n addr -- )`
Store a 16-bit cell at `addr`.

```forth
variable x   42 x !
```

### `C@` `( addr -- b )`
Fetch a byte from `addr`; zero-extended to a cell.

```forth
22528 c@
```
Leaves the attribute byte at the top-left of the screen.

### `C!` `( b addr -- )`
Store the low byte of `b` at `addr`.

```forth
56 22528 c!
```
Writes `56` to the first attribute cell.

### `+!` `( n addr -- )`
Add `n` to the cell at `addr`.

```forth
variable counter   1 counter +!
```

### `CMOVE` `( src dst count -- )`
Copy `count` bytes from `src` to `dst`, low addresses first.

```forth
source-buf dest-buf 32 cmove
```

### `FILL` `( addr count byte -- )`
Fill `count` bytes starting at `addr` with `byte`.

```forth
22528 768 56 fill
```
Paints the whole attribute area white-on-black.

---

## Spectrum I/O

### `BORDER` `( n -- )`
Set the border colour (0–7); writes to port `$FE`.

```forth
2 border
```
Sets the border to red.

```forth
: flash  0 begin dup border 1+ again ;
```

---

## Internal (compiled only)

These are emitted by the compiler; they are never written by hand in source.

### `LIT` `( -- n )`
Push the inline 16-bit cell that follows the `LIT` address in the threaded
stream. Compiled automatically when a number appears in a definition.

### `BRANCH` `( -- )`
Unconditional jump; the next cell is the branch target. Compiled by `BEGIN`
/ `AGAIN`.

### `EXIT` `( -- )` `R:( addr -- )`
Return from the current colon definition. Compiled automatically by `;`.
