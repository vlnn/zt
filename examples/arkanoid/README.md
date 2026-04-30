# Arkanoid (zt / ZX Spectrum)

A small arkanoid-like in Forth, built for the [zt](https://github.com/) cross-compiler
targeting the ZX Spectrum.

## Run

Load `arkanoid.sna` in Fuse, ZEsarUX, or any other 48K-compatible Spectrum
emulator.

Controls:

- `O` — paddle left
- `P` — paddle right

Knock out all 128 bricks to wrap to a fresh level. You have 3 lives.

## Source layout

```
arkanoid/
├── main.fs              entry — calls arkanoid then halt
└── lib/
    ├── sprites.fs       ball-shifted, blank-shifted, paddle-{left,mid,right}, brick-tile
    ├── bricks.fs        32×4 brick grid via stdlib grid.fs, ball-center collision
    ├── paddle.fs        char-aligned paddle, throttled O/P motion (paddle-rate=2)
    ├── ball.fs          physics: walls, ceiling, paddle, brick bounces, floor-loss
    ├── score.fs         score, lives, hud-dirty flag
    └── game.fs          init-level, game-step, game-loop, top-level arkanoid
```

## Build from source

Drop the `arkanoid/` directory under `examples/` of a zt checkout and:

```
zt build examples/arkanoid/main.fs -o build/arkanoid.sna
```

## Tests

`test_examples_arkanoid.py` runs the simulator against the built image and
asserts on game state (paddle bounds, brick count, score, etc). Drop it under
`tests/` and run with `pytest tests/test_examples_arkanoid.py`.

## Design notes

- **Sprite mix:** `blit8x` (pre-shifted) for the ball — pixel resolution. `blit8`
  / `blit8c` (char-aligned) for paddle pieces and bricks since they're naturally
  on the 8-pixel grid.
- **One `lock-sprites` for the whole game loop** — interrupts stay disabled the
  whole run, matching the `dynamic.fs` pattern. Lets the final `halt` after
  `dead?` actually halt cleanly.
- **HUD dirty-bit:** `mark-hud-dirty` is set only when score or lives change; per
  frame `maybe-draw-hud` skips the expensive ROM-emit path most of the time.
- **Cached brick count:** `brick-count` is a single variable, so `bricks-alive`
  is one `@` instead of iterating 128 cells per frame.
