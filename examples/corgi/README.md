# Corgi (zt example)

A tiny line-based text adventure. A small dog dropped their red ball into
the spooky old well; you, the goodest corgi, must fetch it home.

## World

Five rooms, three items.

```
   well
    |
   road
    |
  garden
    |
  hallway
    |
  kitchen   (start)
```

The well is too scary to enter empty-pawed — pick up the stick from the
garden first. Drop the ball in the kitchen to win.

## Build

```
zt build examples/corgi/main.fs -o build/corgi.sna
```

Load `corgi.sna` in Fuse, ZEsarUX, or any 48K-compatible emulator.

## Commands

Type a verb and press ENTER. The first letter is enough — `n` and `north`
both go north; `t`, `take`, `g`, `get` all pick up.

| Verb | Action |
|------|--------|
| N S E W | move |
| LOOK | describe surroundings |
| TAKE / GET | grab the thing here |
| DROP | drop something |
| INV | inventory |
| BARK | WOOF! |
| HELP | help (or `?`, if your keyboard makes one) |
| QUIT | stop the game |

## Display model

Each turn the screen is cleared and redrawn:

```
<result of last action>

<current room description>
<items here>

>
```

zt's `EMIT` doesn't scroll at row 24 (it wraps to row 0), so this
clear-and-redraw approach is what fits the constraint. The "result of
last action" is set by each command via a `last-msg` enum and rendered
by `show-msg` at the top of the next turn.

## Tests

The Forth-side assertions live in `tests/test_corgi.fs` and run via the
project's standard test harness:

```
pytest examples/corgi/tests/test_corgi.fs
```

The Python-side compilation and behaviour tests:

```
pytest examples/corgi/tests/test_corgi.py
```

## Source layout

```
corgi/
├── main.fs              entry point
├── app/
│   ├── world.fs         rooms, exits, items
│   └── game.fs          descriptions, parsing, dispatch, render loop
└── tests/
    ├── test_corgi.fs    pure-Forth assertion tests
    └── test_corgi.py    Python integration tests
```

## Design notes

- **Line input** via a pure-Forth `read-line`, adapted from
  `examples/zlm-tinychat/main.fs`. A 32-byte command buffer; ENTER
  (CR = 13) ends the line.
- **First-letter dispatch** sidesteps the `COMPARE`/`>UPPER` gap that
  `FORTH-ROADMAP.md` calls out. `first-char` lowercases the first
  non-space byte of the buffer; `dispatch` then looks the byte up in
  the parallel `cmd-keys` / `cmd-actions` arrays via `index-of?-byte`
  from `array-hof.fs`.
- **Data-driven world**: `rooms`, `edge-from`/`edge-to`/`edge-dir`,
  `item-loc`, `item-homes`, `item-printers`, `msg-printers`,
  `cmd-keys`, and `cmd-actions` are all `w:` / `c:` array literals.
  Adding a corridor is one row across the three edge arrays; adding
  a verb is one byte in `cmd-keys` and one xt in `cmd-actions`.
  `init-exits` clears every room with `for-each-word`, then walks
  the edges and applies `connect-pair`, which uses `1 xor` to flip
  to the opposite direction.
- **Single source of truth for items**: an item lives in exactly one
  place — a room, the player's jaws (`carried`), or `nowhere` —
  and `item-loc[id]` *is* that place. No bit-bitmap, no bookkeeping
  on `take`/`drop`. `pick-at` finds the first item in a given place
  with `index-of?-word`.
- **Deferred messages**: each `do-*` command updates state and sets
  `last-msg` (a small enum) instead of printing. `show-msg` is just
  `last-msg @ msg-printers swap a-word@ execute` — the enum doubles
  as an array index. `render` clears the screen, runs `show-msg`
  for the previous action, then draws the current room.
