# Arkanoid (zt / ZX Spectrum)

A small arkanoid-like in Forth, built for the [zt](https://github.com/) cross-compiler
targeting the ZX Spectrum.

## Run

Load `arkanoid.sna` in Fuse, ZEsarUX, or any other 48K-compatible Spectrum
emulator.

Controls:

- `O` — paddle left
- `P` — paddle right

Knock out all 120 bricks to wrap to a fresh level. You have 3 lives.

## Source layout

```
arkanoid/
├── main.fs              entry — calls arkanoid then halt
└── lib/
    ├── sprites.fs       ball-shifted, blank-shifted, paddle-{left,mid,right}, brick-tile, wall-tile
    ├── bricks.fs        30×4 brick grid via stdlib grid.fs, ball-center collision
    ├── paddle.fs        char-aligned paddle, throttled O/P motion, paddle-vel tracking
    ├── ball.fs          physics: walls, ceiling, paddle (zone-based), brick bounces, floor-loss
    ├── score.fs         score, lives, hud-dirty flag
    └── game.fs          init-level, game-step, game-loop, top-level arkanoid
```

## Build from source

Drop the `arkanoid/` directory under `examples/` of a zt checkout and:

```
zt build examples/arkanoid/main.fs -o build/arkanoid.sna
```

## Tests

`tests/test_arkanoid.py` builds the example end-to-end and asserts on
game state (paddle bounds, brick count, score, paddle pixel integrity,
ball-dx variation, no pixel trails). Run with
`pytest examples/arkanoid/tests/test_arkanoid.py`.

## Design notes

- **Sprite mix:** `blit8x` (pre-shifted) for the ball — pixel resolution.
  `blit8` / `blit8c` (char-aligned) for paddle pieces and bricks since they're
  naturally on the 8-pixel grid.
- **One `lock-sprites` for the whole game loop** — interrupts stay disabled
  the whole run. Lets the final `halt` after `dead?` actually halt cleanly.
- **Frame ordering:** render at the start of the frame (top border), physics
  at the end. The visible image is finalised before the beam reaches it.
- **Cell-level restore:** before painting the ball, repaint each previously-
  occupied cell to its background (live brick, blank, etc). Smart-skip the
  second cell-row when the ball was cell-aligned vertically.
- **`ball-moved?` predicate:** restore fires on any pixel-level movement,
  not just cell-index change — sub-cell motion still shifts the blit's
  16x8-pixel footprint and would otherwise leave a trail.
- **Variable bounce angles:** the paddle is split into six 4-pixel zones
  giving the ball `dx ∈ {-3,-2,-1,+1,+2,+3}` based on contact point. The
  paddle's per-frame column delta (`paddle-vel`) adds extra "english".
- **HUD dirty-bit:** `mark-hud-dirty` is set only when score or lives change;
  per frame `maybe-draw-hud` skips the expensive ROM-emit path most of the
  time. The static "SCORE " / "LIVES " labels are drawn once at game start;
  only the digits are re-emitted.
- **Cached brick count:** `brick-count` is a single variable, so
  `bricks-alive` is one `@` instead of iterating the grid each frame.
- **`ball-max-y = paddle-top-px - 8`:** the ball is declared lost the
  moment it reaches paddle level without a horizontal overlap, so its
  blit never lands on the paddle row and corrupts paddle pixels.

See [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) for the full list of
known limitations and possible extensions.
