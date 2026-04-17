# Z80 Forth Cross-Compiler — Implementation Plan

## Project structure

(subject to change)
```
zt/
├── src/zt/
│   ├── __init__.py
│   ├── asm.py              # Asm class, opcode methods
│   ├── primitives.py        # create_* functions
│   ├── sna.py               # SNA builder
│   ├── sim.py               # Z80 simulator (M1.5)
│   ├── tokenizer.py         # Forth tokenizer (M2)
│   ├── compiler.py          # cross-compiler core (M3)
│   ├── controlflow.py       # IF/BEGIN/DO compilation (M4)
│   ├── io.py                # EMIT/KEY primitives, string support (M5)
│   ├── peephole.py          # peephole optimizer (M7.5)
│   ├── tap.py               # .tap output (M8)
│   └── cli.py               # forthc entry point (M6)
├── tests/
│   ├── test_asm.py
│   ├── test_primitives.py
│   ├── test_sim.py
│   ├── test_tokenizer.py
│   ├── test_compiler.py
│   ├── test_controlflow.py
│   ├── test_io.py
│   ├── test_peephole.py
│   ├── test_tap.py
│   └── test_integration.py
├── stdlib/
│   ├── core.fs              # core words defined in Forth
│   ├── screen.fs            # Spectrum screen helpers
│   ├── math.fs              # extended math
│   └── string.fs            # string handling
├── examples/
│   ├── border-plasma.fs
│   ├── attr-fill.fs
│   ├── hello.fs
│   ├── sierpinski.fs
│   ├── snake.fs
│   └── ...
├── pyproject.toml
└── README.md
```

---

## M0 — Refactor existing code into project structure ✅

### Deliverable

Same functionality, clean package layout, `forthc` is installable.

---

## M1 — Primitive library expansion ✅

### Implemented primitives

#### Stack operations
ROT, NIP, TUCK, 2DUP, 2DROP, 2SWAP, >R, R>, R@

#### Arithmetic
1+, 1-, 2*, 2/, NEGATE, ABS, MIN, MAX

#### Logic and comparison
AND, OR, XOR, INVERT, LSHIFT, RSHIFT, =, <>, <, >, 0=, 0<, U<

#### Memory
C@, C!, +!, CMOVE, FILL

### Asm extensions added
- `alias()` method for dual naming (e.g. PLUS / +)
- Relative jumps: `jr_to`, `jr_z_to`, `jr_nz_to`, `jr_c_to`, `jr_nc_to`, `djnz_to`
  with separate `rel_fixups` list for 1-byte signed displacement resolution
- Conditional absolute jumps: `jp_z`, `jp_nz`, `jp_p`, `jp_m`
- ~35 new opcode methods for shifts, bit ops, 8-bit loads, logic, block transfer

All primitives have both uppercase labels (PLUS) and Forth-style aliases (+).

### Deliverable

~45 working primitives with byte-sequence tests for each. 219 tests passing.

---

## M1.25 — Multiply and divide primitives

### Why (split from M1)

Software multiply and divide are significantly more complex (~30-40 lines each)
than the other M1 primitives. They are deferred to keep M1 focused and testable.
They can be implemented either before or in parallel with M1.5 (simulator), but
behavioral correctness is best validated with the simulator.

### Primitives to implement

| Word | Stack effect | Notes |
|------|-------------|-------|
| `*` | ( a b -- a*b ) | Software multiply, shift-and-add, 16 iterations |
| `/MOD` | ( a b -- rem quot ) | Software divide, restoring division, 16 iterations |
| `/` | ( a b -- quot ) | /MOD then NIP |
| `MOD` | ( a b -- rem ) | /MOD then DROP |
| `U*` | ( a b -- ud ) | Unsigned 16×16→32 if needed |

Implementation notes for multiply:
```
; HL = a, stack has b
; Result in HL
; Use DE as multiplicand, B as bit counter
; Standard shift-and-add loop, 16 iterations
```

Implementation notes for divide:
```
; Dividend in DE (popped), divisor in HL
; Use restoring division or non-restoring
; 16 iterations, result in HL, remainder in DE (or vice versa)
; Must handle divide-by-zero (return 0 or -1, pick one)
```

### Actions

1. Implement multiply primitive. Test byte sequence.
2. Implement /MOD primitive. Test byte sequence.
3. Implement / and MOD as thin wrappers.
4. Add to PRIMITIVES list.
5. Behavioral tests added once M1.5 (simulator) is available.

---

## M1.5 — Z80 simulator ✅

### Design

A minimal Z80 emulator in Python. Only supports the opcodes we compile — not a general Z80 emulator. Runs a compiled image and returns final machine state.

```python
@dataclass
class Z80State:
    pc: int = 0
    sp: int = 0
    ix: int = 0
    iy: int = 0
    hl: int = 0
    de: int = 0
    bc: int = 0
    af: int = 0
    hl_alt: int = 0
    de_alt: int = 0
    bc_alt: int = 0
    af_alt: int = 0
    memory: bytearray = field(default_factory=lambda: bytearray(65536))
    halted: bool = False
    cycles: int = 0
    iff: bool = False
```

### Opcode coverage needed

Only what our primitives use. Roughly 40-50 distinct opcodes:
- LD group: r,r / r,(hl) / (hl),r / r,n / rp,nn / (nn),sp / sp,(nn)
- LD with IX/IY: r,(ix+d) / (ix+d),r / ix,nn / iy,nn / (iy+d),r / r,(iy+d)
- Stack: PUSH/POP for HL, DE, BC, AF, IX, IY
- Arithmetic: ADD HL,rp / INC/DEC rp / INC/DEC r / ADD/SUB/AND/OR/XOR/CP A,r
- 16-bit: SBC HL,DE / ADC HL,DE
- Shifts: SRA/SRL/RR/RL on H, L
- Bit: BIT n,r
- Branch: JP nn / JP (HL) / JR e / JR cc,e / DJNZ e / CALL nn / RET / RET cc
- Block: LDIR
- I/O: OUT (n),A / IN A,(n)
- Misc: EX DE,HL / EX (SP),HL / EXX / DI / EI / HALT / NOP / CPL / SCF / CCF

### Actions

1. Implement `Z80` class with `step()` method that decodes and executes one instruction.

2. Implement `run(max_cycles)` that loops `step()` until HALT or cycle limit.

3. Implement opcode decode for unprefixed opcodes (0x00–0xFF).

4. Implement opcode decode for CB-prefixed opcodes (bit/shift).

5. Implement opcode decode for DD-prefixed opcodes (IX).

6. Implement opcode decode for FD-prefixed opcodes (IY).

7. Implement opcode decode for ED-prefixed opcodes (LDIR, SBC HL, etc.).

8. Add helper: `load_image(code, origin)` — places code bytes in memory at origin.

9. Add helper: `data_stack(state) -> list[int]` — reads the data stack by walking
   from current SP up to the initial SP, returning the values. Includes TOS from HL.

10. Add helper: `return_stack(state) -> list[int]` — same for IY-based return stack.

11. Add `run_forth(cells, initial_stack=()) -> list[int]`:
    - Builds a minimal image (START + primitives + the given cells + HALT)
    - Loads into simulator
    - Runs
    - Returns the data stack contents

12. Add I/O capture: `OUT` instructions to port 0xFE go into a list, so border
    effects can be tested.

### Tests

Simulator tests are in two groups:

**Unit tests for individual opcodes:**
```python
@pytest.mark.parametrize("opcode,setup,expected_hl", [
    (0x23, {"hl": 0x0001}, 0x0002),   # INC HL
    (0x2B, {"hl": 0x0001}, 0x0000),   # DEC HL
    (0x19, {"hl": 5, "de": 3}, 8),    # ADD HL,DE
])
def test_opcode(opcode, setup, expected_hl):
    ...
```

**Integration tests for Forth primitives:**
```python
@pytest.mark.parametrize("cells,expected_stack", [
    ([LIT, 3, LIT, 4, PLUS],        [7]),
    ([LIT, 10, LIT, 3, MINUS],      [7]),
    ([LIT, 7, DUP, PLUS],           [14]),
    ([LIT, 5, LIT, 3, SWAP],        [3, 5]),
    ([LIT, 1, LIT, 2, LIT, 3, ROT], [2, 3, 1]),
    ([LIT, 6, LIT, 7, STAR],        [42]),
])
def test_forth_primitive(cells, expected_stack):
    result = run_forth(cells)
    assert result == expected_stack
```

### Deliverable

A working simulator that can run any combination of primitives and assert on
the resulting stack. Foundation for all future compiler tests.

### Demo

Trace output of the border-plasma demo showing instruction-by-instruction
execution with cycle counts. Proves the simulator matches real hardware behavior.

---

## M2 — Tokenizer ✅

### Design

```python
@dataclass
class Token:
    value: str
    kind: Literal["word", "number", "string"]
    line: int
    col: int
    source: str   # filename

def tokenize(text: str, source: str = "<input>") -> list[Token]:
    ...
```

### Rules

- Whitespace (space, tab, newline) separates tokens.
- `\` starts a line comment — skip to end of line.
- `(` starts a block comment — skip to matching `)`. No nesting.
- `."` starts a string — read until next `"`. Compile as a single string token.
- `s"` same as `."` but different semantic (handled by compiler).
- `char X` — next non-whitespace character becomes a number token (its ASCII value).
- Numbers: plain decimal, `$` prefix for hex, `%` prefix for binary, `-` prefix for negative.
- Everything else is a word token, case-insensitive (lowercased on output).

### Actions

1. Write the tokenizer as a single function with a position cursor.
   No regex — manual character-by-character scan. Forth's lexing rules are
   simple enough that a state machine in a single function is clearest.

2. Handle edge cases: empty input, consecutive whitespace, comments at end of
   file without trailing newline, unclosed `(` comment (error), unclosed string (error).

3. Track line/col for error reporting.

### Tests

```python
@pytest.mark.parametrize("src,expected_values", [
    (": foo 1 + ;",           [":", "foo", "1", "+", ";"]),
    ("1 2 + \\ comment",      ["1", "2", "+"]),
    ("( block ) 3",           ["3"]),
    ('.\" hello\" 4',          ['.\"', "hello", "4"]),
    ("$FF",                   ["$ff"]),
    ("%1010",                 ["%1010"]),
    ("-42",                   ["-42"]),
])
def test_tokenize_values(src, expected_values): ...

def test_unclosed_string_raises(): ...
def test_unclosed_paren_raises(): ...
def test_empty_input_returns_empty(): ...
def test_line_col_tracking(): ...
```

### Deliverable

`tokenize()` function. ~80 lines of Python.

---

## M3 — Compiler core ✅

### Design

```python
@dataclass
class Word:
    name: str
    address: int
    kind: Literal["prim", "colon", "variable", "constant"]
    immediate: bool = False
    compile_action: Callable | None = None   # for immediate words

@dataclass
class CompileError(Exception):
    message: str
    token: Token | None = None

class Compiler:
    def __init__(self, asm: Asm):
        self.asm = asm
        self.words: dict[str, Word] = {}
        self.state: Literal["interpret", "compile"] = "interpret"
        self.control_stack: list[int] = []
        self.current_word: str | None = None

    def register_primitives(self):
        """Compile all asm primitives and register them in self.words."""

    def compile_source(self, text: str, source: str = "<input>"):
        """Tokenize and compile a source string."""

    def compile_token(self, tok: Token):
        """Process a single token in current state."""

    def compile_literal(self, value: int):
        """Compile LIT + value cells."""

    def build(self) -> bytes:
        """Resolve all labels and return the raw image bytes."""
```

### Compilation rules

**Interpret state** (outside `:` definition):
- Known word → execute its compile_action (if it has one) or error
  (in a cross-compiler, interpreting non-immediate words doesn't make sense —
  we're not running on the target).
- Number → allowed only in specific contexts (e.g., after `VARIABLE`)
- `:` → switch to compile state, start new word
- `VARIABLE`, `CONSTANT`, `CREATE` → handled as interpret-state directives

**Compile state** (inside `:` definition):
- Known word, not immediate → compile its address as a cell
- Known word, immediate → call its compile_action
- Number → compile `LIT <n>`
- `;` → compile EXIT, close word, switch to interpret state

### Immediate words to implement in M3

Only the basics — control flow deferred to M4:

| Word | Action |
|------|--------|
| `:` | Start compiling. Record name, compile `CALL DOCOL`. |
| `;` | Compile `EXIT`. Register word. Switch to interpret state. |
| `LITERAL` | Compile `LIT <value>`. |
| `[` | Switch to interpret state temporarily. |
| `]` | Switch back to compile state. |
| `[']` | Look up next word, compile `LIT <its-address>`. |
| `RECURSE` | Compile current word's address (self-reference). |
| `'` | Look up next word. In interpret state, push address. |

### Interpret-mode directives

| Word | Action |
|------|--------|
| `VARIABLE name` | Allocate 2 bytes in target RAM, register name as word that pushes the address. Compile a `DOVAR`-style stub: `push hl; ld hl,<addr>; jp NEXT`. |
| `CONSTANT name` | Next token is the value. Register name as word that pushes the literal. Compile: `push hl; ld hl,<value>; jp NEXT`. |
| `CREATE name` | Like VARIABLE but no automatic allocation — user `,`'s data after it. |
| `,` | Compile a cell (2 bytes) into the image at HERE. |
| `C,` | Compile a single byte. |
| `ALLOT` | Advance HERE by n bytes. |

### Actions

1. Implement `Word` dataclass and `Compiler.__init__`.

2. Implement `register_primitives()` — calls each `create_*` function,
   then registers the label as a Word entry in `self.words`.

3. Implement `compile_source()` — tokenize, iterate, call `compile_token` per token.

4. Implement `compile_token()` — the interpret/compile dispatch.

5. Implement `create_literal()`.

6. Implement `:` and `;`.

7. Implement `VARIABLE`, `CONSTANT`, `CREATE`, `,`, `C,`, `ALLOT`.

8. Implement `LITERAL`, `[`, `]`, `[']`, `RECURSE`.

9. Implement `is_number()` and number parsing (decimal, hex, binary).

10. Implement error reporting with line/col from token.

11. Wire into `build_image`: compiler replaces the old hand-built demo.

12. Compile and run first `.fs` program using the simulator.

### Tests

**Compiler unit tests:**
```python
def test_colon_definition_creates_docol():
    c = make_compiler()
    c.compile_source(": double dup + ;")
    assert "double" in c.words
    # check that the image contains CALL DOCOL, DUP addr, PLUS addr, EXIT addr

def test_literal_creates_lit_cell():
    c = make_compiler()
    c.compile_source(": five 5 ;")
    # body should be: CALL DOCOL, LIT, 5, EXIT

def test_variable_allocates_two_bytes(): ...
def test_constant_pushes_value(): ...
def test_unknown_word_raises(): ...
def test_nested_colon_raises():
    # : foo : bar ;  — should error
```

**Integration tests via simulator:**
```python
@pytest.mark.parametrize("src,expected", [
    (": double dup + ; 21 double", [42]),
    (": sq dup * ; 7 sq", [49]),
    ("variable x  5 x !  x @", [5]),
    ("10 constant ten  ten ten +", [20]),
])
def test_compile_and_run(src, expected):
    assert compile_and_run(src) == expected
```

### Deliverable

Working cross-compiler for flat (no control flow) Forth definitions.
Can compile `: square dup * ;` from source and run it on the simulator.

### Demo

`counter.fs` — the existing demo rewritten as Forth source:
```forth
: main  0 begin dup border 1+ again ;
```

Wait — `BEGIN`/`AGAIN` aren't implemented until M4. So the M3 demo uses `BRANCH` explicitly:

Actually, `BEGIN`/`AGAIN` should be among the first control words. Let me revise — M3 gets just `BEGIN`/`AGAIN` (the simplest control pair), and M4 does the rest.

Add to M3 immediate words:
- `BEGIN` — push current HERE onto control stack.
- `AGAIN` — creates `BRANCH` + address from control stack.

Now `counter.fs` compiles.

---

## M4 — Control flow

### Immediate words to implement

Each one manipulates the control stack and creates `BRANCH`/`0BRANCH` cells.

#### Conditional (forward jumps)

| Word | Action |
|------|--------|
| `IF` | Compiles `0BRANCH` + placeholder cell. Push placeholder offset onto control stack. |
| `THEN` | Pop control stack. Patch the placeholder to current HERE. |
| `ELSE` | Compiles `BRANCH` + new placeholder. Patch old placeholder (from `IF`) to HERE. Push new placeholder. |

#### Loops (backward jumps)

Already have `BEGIN`/`AGAIN` from M3. Add:

| Word | Action |
|------|--------|
| `UNTIL` | Creates `0BRANCH` + address from control stack (back to BEGIN). |
| `WHILE` | Creates `0BRANCH` + placeholder. Push placeholder. Swap top two control stack entries (so REPEAT can find both). |
| `REPEAT` | Pop control stack → patch WHILE's placeholder to HERE. Pop again → create `BRANCH` back to BEGIN address. |

#### Counted loops

These need runtime primitives `(DO)`, `(LOOP)`, `(+LOOP)`, `I`, `J`, `UNLOOP`, `LEAVE`.

| Word | Action |
|------|--------|
| `DO` | Create `(DO)`. Push HERE (loop body start) and a leave-patch list onto control stack. |
| `LOOP` | Create `(LOOP)` + address of loop body. Patch all LEAVE targets to HERE. |
| `+LOOP` | Same but create `(+LOOP)`. |
| `I` | Create `I` (reads loop index from return stack). |
| `J` | Create `J` (reads outer loop index). |
| `LEAVE` | Create `BRANCH` + placeholder. Add to leave-patch list. |
| `UNLOOP` | Compile `UNLOOP` (clean up return stack without branching). |

**Runtime primitive `(DO)`:**
```
; ( limit index -- )  R:( -- limit index )
; Push limit and index onto return stack
(DO):   pop  de              ; DE = limit
        ; push limit then index onto return stack
        dec  iy : dec iy
        ld   (iy+0),e : ld (iy+1),d    ; limit
        dec  iy : dec iy
        ld   (iy+0),l : ld (iy+1),h    ; index (TOS)
        pop  hl              ; new TOS
        jp   NEXT
```

**Runtime primitive `(LOOP)`:**
```
; Increment index on return stack. If index == limit, exit loop (skip branch target).
; Otherwise branch back (like BRANCH — target follows inline).
(LOOP): ld   e,(iy+0) : ld d,(iy+1)    ; DE = index
        inc  de
        ld   (iy+0),e : ld (iy+1),d    ; write back
        ld   a,(iy+2) : push af         ; A = limit low
        ld   a,(iy+3)                   ; A = limit high
        cp   d
        jr   nz, loop_continue
        pop  af
        cp   e
        jr   z, loop_exit
        push af     ; dummy for the pop below
loop_continue:
        pop  af     ; discard saved limit low
        ; branch back (same as BRANCH)
        ld   e,(ix+0) : ld d,(ix+1)
        push de : pop ix
        jp   NEXT
loop_exit:
        pop  af
        inc  ix : inc ix    ; skip branch target
        ; clean up return stack
        inc  iy : inc iy    ; drop index
        inc  iy : inc iy    ; drop limit
        jp   NEXT
```

**Runtime primitive `I`:**
```
I:      push hl
        ld   l,(iy+0) : ld h,(iy+1)
        jp   NEXT
```

**Runtime primitive `J`:**
```
J:      push hl
        ld   l,(iy+4) : ld h,(iy+5)   ; skip past inner loop's index+limit
        jp   NEXT
```

### Control stack validation

Add tag bytes to control stack entries to catch mismatches:

```python
IF_TAG = "if"
BEGIN_TAG = "begin"
DO_TAG = "do"

def push_control(self, addr, tag):
    self.control_stack.append((addr, tag))

def pop_control(self, expected_tag):
    if not self.control_stack:
        raise CompileError("control stack underflow")
    addr, tag = self.control_stack.pop()
    if tag != expected_tag:
        raise CompileError(f"expected {expected_tag}, got {tag}")
    return addr
```

### Actions

1. Implement `0BRANCH` runtime primitive in `primitives.py`. Test byte sequence.

2. Implement `IF`, `THEN`, `ELSE` as immediate words in `compiler.py`.

3. Implement `UNTIL` as immediate word.

4. Implement `WHILE`, `REPEAT` as immediate words.

5. Implement `(DO)`, `(LOOP)`, `(+LOOP)`, `I`, `J`, `UNLOOP` as runtime primitives.

6. Implement `DO`, `LOOP`, `+LOOP`, `LEAVE` as immediate words.

7. Implement control stack validation with tags and clear error messages.

8. Test error cases: mismatched `IF`/`LOOP`, unclosed `:`, etc.

### Tests

```python
@pytest.mark.parametrize("src,expected", [
    # IF/THEN
    ("0 if 42 then 99",                  [99]),
    ("1 if 42 then 99",                  [42, 99]),
    # IF/ELSE/THEN
    ("0 if 10 else 20 then",            [20]),
    ("1 if 10 else 20 then",            [10]),
    # Nested IF
    ("1 if 1 if 42 then then",          [42]),
    ("1 if 0 if 42 else 99 then then",  [99]),
    # BEGIN/UNTIL
    ("0 begin 1+ dup 5 = until",         [5]),
    # BEGIN/WHILE/REPEAT
    ("0 begin dup 5 < while 1+ repeat",  [5]),
    # DO/LOOP
    ("0 10 0 do 1+ loop",               [10]),
    ("0 5 0 do i + loop",               [10]),    # 0+1+2+3+4
    # Nested DO/LOOP
    ("0 3 0 do 3 0 do 1+ loop loop",    [9]),
    # LEAVE
    ("10 0 do i 5 = if leave then loop i", [...]),
])
def test_control_flow(src, expected):
    assert compile_and_run(src) == expected

def test_mismatched_if_loop_raises(): ...
def test_unclosed_if_raises(): ...
def test_then_without_if_raises(): ...
```

### Deliverable

Full structured-programming control flow. Any standard Forth tutorial program compiles.

### Demo

`sierpinski.fs`:
```forth
: sierpinski
    24 0 do
        32 0 do
            i j and 0= if
                56
            else
                0
            then
            j 32 * i + 22528 + c!
        loop
    loop ;
: main  sierpinski begin again ;
```

---

## M5 — I/O and strings

### Runtime primitives

| Word | Implementation |
|------|---------------|
| `EMIT` | `ld a,l; rst $10; pop hl; jp NEXT` — uses Spectrum ROM print |
| `KEY` | `push hl; CALL $15E6 (or keyboard port scan); ld l,a; ld h,0; jp NEXT` |
| `KEY?` | push flag if key is available (poll keyboard ports) |
| `TYPE` | ( addr len -- ) loop calling EMIT |

Spectrum-specific startup: before EMIT works, must call ROM routine to open
channel 2 (main screen). Add to `emit_start`:
```asm
    ld   a,2
    call $1601     ; CHAN-OPEN — open channel 2 (upper screen)
```

### String support in the compiler

`."` is an immediate word. At compile time:
1. Read characters until closing `"`.
2. Emit: `LITSTR <inline-length-byte> <inline-string-bytes> TYPE`.

`LITSTR` is a new runtime primitive:
```
LITSTR: push hl
        ; read length byte from (IX), then IX points at string
        ld   l,(ix+0)
        ld   h,0
        inc  ix
        ; push HL (length), then push IX (address)
        push hl
        push ix       ; this gives us the string address
        pop  hl        ; HL = string address (new TOS)
        ; advance IX past the string
        pop  de        ; DE = length
        push de        ; keep length on stack
        ; add length to IX
        ; (need a loop or add-to-ix sequence)
        ex   de,hl     ; DE = addr, HL = length
        add  hl,de     ; HL = past-end of string...
        ; this is getting complicated. simpler approach:
```

Alternative simpler design — store strings in a separate data area, not inline:

`."` compiles to:
1. `LIT <string-address>` — address of string in data area
2. `LIT <length>`
3. `TYPE`

The compiler appends string bytes to a data area at the end of the image.
Simpler runtime, no special LITSTR primitive needed.

### `TYPE` primitive

```
TYPE:   ; ( addr len -- )
        ; HL = len (TOS), second = addr
        ld   b,l        ; B = length (assuming < 256)
        pop  hl         ; HL = addr
.loop:  ld   a,(hl)
        rst  $10        ; ROM print
        inc  hl
        djnz .loop
        pop  hl         ; restore TOS
        jp   NEXT
```

For strings > 255 chars, need a 16-bit counter. For now, cap at 255 — fine
for Spectrum screen (32×24 = 768 chars max visible).

### Number printing

Implement `.` (dot) in Forth, not asm:
```forth
: digit>char  48 + ;
: /digit  ( n -- n/10 n%10 )  10 /mod swap ;
: .digit  digit>char emit ;
: (.)  ( n -- )
    dup 0= if drop 48 emit exit then
    dup 0< if 45 emit negate then
    dup 10 < if .digit exit then
    /digit >r (.) r> .digit ;
: .  (.) space ;
```

Or a simpler iterative version using a buffer.

### Other I/O words to define in Forth

```forth
: cr     13 emit ;
: space  32 emit ;
: spaces ( n -- )  0 do space loop ;
```

### Actions

1. Add `rst_n` opcode method to Asm (single byte: 0xC7 | (n & 0x38)).

2. Add channel-open sequence to `emit_start`.

3. Implement `EMIT` primitive. Test byte sequence.

4. Implement `KEY` primitive. Test byte sequence.

5. Implement `TYPE` primitive. Test byte sequence.

6. Implement `."` as an immediate word in the compiler.

7. Implement `S"` as an immediate word (pushes addr and len without printing).

8. Add string data area management to the compiler.

9. Write number printing in `stdlib/core.fs`.

10. Write `CR`, `SPACE`, `SPACES` in `stdlib/core.fs`.

11. Add I/O capture to the Z80 simulator: intercept `RST $10` and record
    characters. `run_forth` returns output string alongside stack.

### Tests

```python
@pytest.mark.parametrize("src,expected_output", [
    ('65 emit',                "A"),
    ('72 emit 73 emit',       "HI"),
    ('.\" hello\"',            "hello"),
    ('42 .',                   "42 "),
    ('-7 .',                   "-7 "),
    ('cr',                     "\r"),
])
def test_io(src, expected_output):
    _, output = compile_and_run_with_output(src)
    assert output == expected_output
```

### Deliverable

Text output on the Spectrum screen. `." Hello!"` works.

### Demo

`hello.fs`:
```forth
: banner
    ." ==================" cr
    ."   FORTH ON Z80"     cr
    ."   cross-compiled"   cr
    ." ==================" cr ;
: main  banner begin again ;
```

---

## M6 — CLI and build driver

### CLI design

```
forthc build SOURCE [SOURCE ...] -o OUTPUT [options]
forthc inspect OUTPUT --symbols SYMFILE
```

**Build options:**
```
-o, --output PATH          output file (required)
--format sna|bin|tap       auto-detected from extension, or explicit
--origin HEX               load address (default $8000)
--dstack HEX               data stack top (default $FF00)
--rstack HEX               return stack top (default $FE00)
--border N                 initial border color 0-7 (default 7)
--map PATH                 emit symbol map file
--include-dir PATH         additional search path for INCLUDE
--stdlib PATH              path to stdlib/ (default: bundled)
```

### INCLUDE / REQUIRE

Implement as immediate words in the compiler:

```python
def immediate_include(compiler):
    filename = compiler.next_token().value
    path = compiler.resolve_include(filename)
    text = path.read_text()
    tokens = tokenize(text, source=str(path))
    compiler.inject_tokens(tokens)

def immediate_require(compiler):
    filename = compiler.next_token().value
    path = compiler.resolve_include(filename)
    if path not in compiler.included_files:
        compiler.included_files.add(path)
        immediate_include(compiler)
```

`inject_tokens` inserts tokens at the current position in the token stream.
Simple: compiler iterates a deque, INCLUDE prepends to it.

Include resolution: search current file's directory first, then `--include-dir` paths.

### Stdlib

Bundle a `stdlib/` directory with core definitions:

`stdlib/core.fs`:
```forth
: 2+  2 + ;
: 2-  2 - ;
: cell+  2 + ;
: cells  2* ;
: nip  swap drop ;
: tuck  swap over ;
: space  32 emit ;
: cr  13 emit ;
: spaces  0 do space loop ;
\ ... number printing, etc.
```

The CLI automatically includes `stdlib/core.fs` before user source
unless `--no-stdlib` is passed.

### Startup and main word

Convention: the compiler looks for a word named `main` after all source is
compiled. If found, the startup code points IX at `main`'s threaded body.
If not found, error.

### Actions

1. Implement `cli.py` with argparse. `forthc build` subcommand.

2. Implement `INCLUDE` and `REQUIRE`.

3. Implement include-path resolution with `--include-dir`.

4. Write `stdlib/core.fs` with basic utility words.

5. Implement auto-include of stdlib.

6. Implement `main` word detection and startup wiring.

7. Implement output format detection from file extension.

8. Implement `--map` flag and symbol map emission (simple `address name` text file).

9. Package with `pyproject.toml` so `uv pip install -e .` works.

10. Write a `Makefile` or `justfile` for the examples.

### Tests

```python
def test_build_hello(tmp_path):
    src = tmp_path / "hello.fs"
    src.write_text(': main ." hello" begin again ;')
    out = tmp_path / "hello.sna"
    result = run_cli(["build", str(src), "-o", str(out)])
    assert result.returncode == 0
    assert out.exists()
    assert out.stat().st_size == 49179

def test_include_resolves(tmp_path):
    lib = tmp_path / "lib.fs"
    lib.write_text(": double dup + ;")
    main = tmp_path / "main.fs"
    main.write_text('include lib.fs\n: main 21 double begin again ;')
    out = tmp_path / "main.sna"
    run_cli(["build", str(main), "-o", str(out)])
    assert out.exists()

def test_require_deduplicates(tmp_path):
    lib = tmp_path / "lib.fs"
    lib.write_text(": double dup + ;")
    main = tmp_path / "main.fs"
    main.write_text('require lib.fs\nrequire lib.fs\n: main 21 double begin again ;')
    out = tmp_path / "main.sna"
    run_cli(["build", str(main), "-o", str(out)])
    # should not error on duplicate definition

def test_missing_main_raises(tmp_path):
    src = tmp_path / "no-main.fs"
    src.write_text(": foo 1 ;")
    out = tmp_path / "out.sna"
    result = run_cli(["build", str(src), "-o", str(out)])
    assert result.returncode != 0

def test_map_file_compiled(tmp_path): ...
```

### Deliverable

`forthc build hello.fs -o hello.sna` works from command line.
Multi-file projects with `INCLUDE` work. Stdlib is bundled.

### Demo

Multi-file plasma project:
```
src/lib/screen.fs
src/lib/math.fs
src/app/plasma.fs
src/main.fs
```
`forthc build src/main.fs -o plasma.sna --map plasma.map`

---

## M7 — Symbol map and debugging

### Symbol map format

For Fuse debugger:
```
$8000 START
$800C NEXT
$8018 DOCOL
$802A EXIT
...
$80A2 main
$80B0 double
```

For ZEsarUX (slightly different):
```
main = $80A2
double = $80B0
```

### zt inspect

Read a `.sna` + `.fsym` (serialized host dictionary) and print decompiled
threaded code:

```
$ zt inspect plasma.sna --symbols plasma.fsym

: double  ( $80B0 )
    dup + ;
: main  ( $80A2 )
    0 begin dup border 1+ again ;
```

### Actions

1. Compile `.map` file during build (already partially done in M6 via --map flag).

2. Compile `.fsym` file — JSON serialization of the host dictionary:
   `{ "double": {"address": "0x80B0", "kind": "colon", "body": [...]} }`.

3. Implement `zt inspect` subcommand:
   - Load `.fsym`
   - Walk each colon word's body cells
   - Reverse-lookup cell addresses to word names
   - Print as readable Forth

4. Support both Fuse and ZEsarUX symbol formats (auto-detect or `--format` flag).

5. Add source location tracking: each Word records file + line of definition.
   Error messages print `screen.fs:42: unknown word 'foo'`.

### Tests

```python
def test_map_file_contents(tmp_path):
    # build, read map file, assert known words present with hex addresses

def test_fsym_roundtrip(tmp_path):
    # build with --fsym, load fsym, verify word names and addresses match

def test_inspect_output(tmp_path):
    # build, inspect, verify output contains ": double dup + ;"
```

### Deliverable

Debuggable images. Fuse shows word names. `zt inspect` decompiles threaded code.

---

## M7.5 — Peephole optimizer

### Design

Post-pass on the cell buffer before image emission. Each colon definition's
body is a list of cell addresses. Scan for patterns, replace with fused primitives.

```python
@dataclass
class PeepholeRule:
    pattern: list[int]       # addresses to match
    replacement: list[int]   # addresses to compile instead

RULES = [
    PeepholeRule([LIT, 0],           [ZERO]),
    PeepholeRule([LIT, 1],           [ONE]),
    PeepholeRule([LIT, 1, PLUS],     [ONE_PLUS]),
    PeepholeRule([LIT, 1, MINUS],    [ONE_MINUS]),
    PeepholeRule([LIT, 2, STAR],     [TWO_STAR]),
    PeepholeRule([LIT, 2, SLASH],    [TWO_SLASH]),
    PeepholeRule([DUP, FETCH],       [DUP_FETCH]),
    PeepholeRule([SWAP, DROP],       [NIP]),
    PeepholeRule([OVER, OVER],       [TWO_DUP]),
    PeepholeRule([DROP, DROP],       [TWO_DROP]),
]
```

Problem: the cell buffer at this stage contains *addresses*, not word names.
The peephole pass needs to compare against known primitive addresses.

Solution: the compiler gives each word a stable name; peephole rules reference
names; the pass maps names to addresses for the current build.

### Fused primitives to implement

| Name | Replaces | Z80 |
|------|----------|-----|
| `ZERO` | `LIT 0` | push hl; ld hl,0 |
| `ONE` | `LIT 1` | push hl; ld hl,1 |
| `ONE_PLUS` | `LIT 1 +` | inc hl |
| `ONE_MINUS` | `LIT 1 -` | dec hl |
| `TWO_STAR` | `LIT 2 *` | add hl,hl |
| `TWO_SLASH` | `LIT 2 /` | sra h; rr l |
| `DUP_FETCH` | `DUP @` | push hl; ld e,(hl); inc hl; ld d,(hl); ex de,hl |
| `NIP` | `SWAP DROP` | pop de |

### Actions

1. Implement fused primitives in `primitives.py`. Test byte sequences.

2. Implement `peephole.py` with the pattern-matching pass.

3. Hook peephole into the compiler: after compiling a colon definition's body
   cells, run peephole before finalizing.

4. Add `--no-optimize` flag to skip peephole.

5. Add cycle-count comparison in tests: compile with and without peephole,
   run in simulator, compare cycle counts.

### Tests

```python
@pytest.mark.parametrize("src,should_contain,should_not_contain", [
    (": f 0 ;",      ["zero"],      ["lit"]),
    (": f 1 + ;",    ["one_plus"],  ["lit", "plus"]),
    (": f dup @ ;",  ["dup_fetch"], ["dup", "fetch"]),
])
def test_peephole_rewrites(src, should_contain, should_not_contain):
    cells = compile_to_cells(src)
    # assert fused primitive present, originals absent

def test_peephole_preserves_semantics():
    # compile the same program with and without peephole
    # run both in simulator
    # assert identical stack results
```

### Deliverable

Automatic peephole optimization. 15-25% speedup on typical code. Transparent — user doesn't see it unless they inspect.

---

## M8 — .tap output

### TAP format

A `.tap` file is a sequence of blocks. Each block:
```
2 bytes: block length (little-endian, includes flag and checksum)
1 byte:  flag (0x00 = header, 0xFF = data)
N bytes: payload
1 byte:  checksum (XOR of flag + all payload bytes)
```

A loadable program needs two blocks:

**Block 1 — header (flag=0x00, 17 bytes payload):**
```
type:    3 (CODE)
name:    10 bytes, space-padded
length:  2 bytes (data block size)
param1:  2 bytes (load address)
param2:  2 bytes (unused, 32768)
```

**Block 2 — data (flag=0xFF, N bytes payload):**
```
raw code bytes
```

Optionally prepend a BASIC loader:

**Block 0 — BASIC header + block:**
```
10 CLEAR 32767
20 LOAD "" CODE 32768
30 RANDOMIZE USR 32768
```

BASIC programs are tokenized — each keyword is a single byte.
This is fiddly but well-documented. ~50 lines.

### Actions

1. Implement `tap.py` with `build_tap(code, origin, name) -> bytes`.

2. Implement BASIC loader tokenization (or embed a pre-built loader).

3. Add `--format tap` to CLI.

4. Auto-detect from `.tap` extension.

### Tests

```python
def test_tap_block_structure():
    tap = build_tap(b"\x00" * 10, origin=0x8000, name="TEST")
    # verify block count, lengths, checksums

def test_tap_checksum():
    # known input -> known checksum

def test_tap_header_fields():
    # verify type=3, name padded, length correct, param1=origin

def test_tap_loads_in_fuse():
    # optional integration test: feed to fuse --auto-load
```

### Deliverable

`.tap` files that load on real hardware via tape or divMMC.

### Demo

`hello.tap` loaded from tape in Fuse with the classic loading bars visible.

---

## M9 — 128K SNA

### Extended SNA format

After the standard 48K SNA (49179 bytes), append:
```
2 bytes: PC (program counter)
1 byte:  port $7FFD last value
1 byte:  TR-DOS flag (0)
remaining banks: 16KB each, in ascending order, skipping the three already saved
```

The first 48K of RAM in the standard part is: bank 5 (0x4000–0x7FFF), bank 2
(0x8000–0xBFFF), and the currently paged bank (0xC000–0xFFFF).

### Changes

1. In 128K mode, PC goes in the extension — not pushed on stack. This is
   simpler than the 48K trick.

2. SP in header is the real SP (no PC-push adjustment needed).

3. Need to track which bank is paged at snapshot time.

### Actions

1. Add `build_sna_128k(code, origin, banks, ...) -> bytes` to `sna.py`.

2. Add `--128k` flag to CLI.

3. Implement bank management: `Compiler.bank(n)` directive that switches
   the current compile target to a specific bank. Code in bank N lives at
   0xC000–0xFFFF in the target address space.

4. Add bank-switch helper primitive: writes to port $7FFD.

### Tests

```python
def test_128k_sna_size():
    # 131103 bytes for 5 extra banks, or 147487 for 8 total

def test_128k_pc_in_extension():
    # PC at byte 49179, not on stack

def test_128k_bank_order():
    # remaining banks in ascending order, skip already-saved ones
```

### Deliverable

128K snapshots. Bank switching from Forth. AY chip access.

### Demo

AY music player — simple chip-tune playing from bank-stored pattern data.

---

## M10 — Polish and long tail

### 10a — Inline NEXT optimization

Add `--inline-next` flag. Each primitive compiles the NEXT body at the end
instead of `JP NEXT`. ~10% speedup, costs ~500 bytes of code space.

Implementation: add `Asm.inline_next()` method that compiles the NEXT body.
Change every `a.jp("NEXT")` to `a.dispatch()` which checks the flag.

### 10b — Primitive inlining

For each primitive, store its raw Z80 bytes as `inline_body`. During
compilation, for sequences of primitives, paste their bodies directly
instead of compiling cell references. Eliminates NEXT dispatch for inlined code.

Add `--inline-primitives` flag. Add size threshold (default: inline if
body ≤ 8 bytes).

### 10c — CODE / END-CODE

Immediate words that switch the compiler into inline-asm mode. Each Z80
mnemonic is registered as an immediate word that compiles its opcode:

```forth
code fast-fill  ( addr count byte -- )
    \ asm mnemonics here
end-code
```

The mnemonics are registered by a setup function that creates one immediate
word per opcode: `ld-a-l,`, `push-hl,`, `di,`, `ei,`, etc.

### 10d — .z80 snapshot output

More capable than SNA: supports 128K natively, optional RLE compression,
version 3 format for maximum compatibility.

### 10e — Conditional compilation

```forth
[defined] AY [if]
    include ay-music.fs
[then]
```

`[DEFINED]`, `[UNDEFINED]`, `[IF]`, `[ELSE]`, `[THEN]` as immediate words.
The compiler maintains a set of defined symbols; `[IF]` skips tokens when
the condition is false.

### 10f — Live reload

```bash
zt watch src/main.fs -o game.sna --emulator fuse
```

Uses `watchdog` or `inotify` to monitor `.fs` files. On change: rebuild,
signal emulator to reload snapshot.

### 10g — Profile output

After running in the simulator, create a report:
```
Word        Calls    Cycles   Avg    % of total
main        1        985432   985432 100.0
draw-sprite 128      412800   3225   41.9
clear-attr  1        89000    89000  9.0
...
```

### 10h — SP-blast primitives

The graphics primitives discussed earlier. Provide a library of:
- `sp-fill` ( src dst count -- ) — blast N bytes using SP trick
- `sp-copy` ( src dst count -- ) — same but arbitrary source
- `attr-fill` ( byte -- ) — fill all 768 attribute bytes

Implement as `CODE` words once 10c is available, or as Python-level primitives.

---

## Dependency graph

```
M0 (refactor) ✅
└── M1 (primitives) ✅ + M1.25 (mul/div) + M1.5 (simulator) — parallel
    └── M2 (tokenizer)
        └── M3 (compiler core)
            └── M4 (control flow)
                ├── M5 (I/O)
                │   └── M6 (CLI + build driver)
                │       ├── M7 (symbol map + debugging)
                │       │   └── M7.5 (peephole optimizer)
                │       ├── M8 (.tap output)
                │       └── M9 (128K SNA)
                └── M10 (long tail, any order)
```

M1 and M1.5 can proceed in parallel — you can write primitives (testing only
byte sequences) while building the simulator, then add behavioral tests once
the simulator is ready.

M1.25 (multiply/divide) can be done before or during M1.5 — byte-sequence tests
only until the simulator is available for behavioral validation.

M8 and M9 are independent of each other and of M7/M7.5.

M10 items are all independent and can be tackled in any order based on what
you need for your current project.
