# Structs (zt example)

A small RPG-flavoured demo that exercises every struct-related feature added
in Phase 5 of the compiler:

- `--`, `STRUCT`, `record` directives for declaring layouts and instances
- Static-instance fusion: `hero .hp >c!` collapses to one Z80 absolute-store
- Dynamic-instance fusion: `.hp >c@` inside an accessor colon collapses to
  one `ADD HL,DE`+deref sequence
- Inheritance via stacked `STRUCT`s (`/boss` extends `/actor`)
- The four canonical surface words `>@`, `>!`, `>c@`, `>c!`, defined with
  `::` so the unfused fallback path is still inline native code

## What the program does

Three actors face off for one round:

| actor   | start hp | takes | end hp |
|---------|----------|-------|--------|
| hero    | 100      | 10 + 30 = 40 | 60 |
| goblin  | 30       | 25    | 5  |
| troll   | 80       | 0     | 80 |

When the program halts, the final HP values are left on the data stack so
a test can verify them. `print-results` also writes the same data to the
Spectrum screen via `cls`/`u.`/`."` for visual inspection.

## Layout

```
0
2 -- .x          \ cell  (offset 0)
2 -- .y          \ cell  (offset 2)
1 -- .hp         \ byte  (offset 4)
1 -- .mp         \ byte  (offset 5)
STRUCT /actor    \ total: 6 bytes

/actor           \ resume from /actor's size = 6
2 -- .rage       \ cell  (offset 6)
STRUCT /boss     \ total: 8 bytes

/actor record hero
/actor record goblin
/boss  record troll
```

A `record` is `create name N allot` in disguise: it emits a CREATE-shaped
variable shim plus N zero bytes of data area.

## What fuses

`setup-actors` writes 13 fields and ends up with 13 `NativeStore` cells in
its IR — each of those is one threaded primitive call (`(!abs)` or `(c!abs)`)
plus a 16-bit absolute address operand. No `+`, no `!`, no `c!` survive the
fusion pass.

The five generic accessor colons (`actor-x`, `actor-y`, `actor-hp`,
`actor-mp`, `boss-rage`) and four mutators each compile to a body of
exactly two cells: one `NativeOffsetFetch` or `NativeOffsetStore`, then
`exit`. The instance is whatever the caller put on the data stack.

Run `python -c "..."` over the IR to confirm; the test file does this in
`TestDynamicFusionFiresInAccessorColons`.

## Files

```
examples/structs/
    main.fs                    entry point
    app/menagerie.fs           struct definitions, records, accessors, sim
    tests/test_structs.py      structural and behavioural tests
    README.md                  this file
```

## Build

```
make build/structs.sna
```

## Test

```
uv run pytest examples/structs/tests/
```
