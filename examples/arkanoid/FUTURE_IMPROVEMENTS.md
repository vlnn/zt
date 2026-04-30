# Future improvements

A working list of known limitations and natural extensions for this build,
grouped by where the effort would land. Each item names the file(s) it would
touch so readers don't have to grep.

## Gameplay

### Ball launch instead of auto-start
After `ball-reset` the ball immediately starts moving. A "press P to launch"
phase would let the player position the paddle first. Implementation:
`ball.fs` adds a `ball-launched?` flag, `ball-physics` short-circuits when
unset, `ball-paint` keeps drawing the ball glued to the paddle, and a key
poll in `game-step` flips the flag.

### Paddle-relative launch direction
A more interesting variant of the above: the launch dx depends on which side
of the paddle the player tilts to (or on `paddle-vel` at launch time), so the
opening angle is the player's choice rather than fixed `+2`.

### Levels and brick layouts
`bricks-fill-alive` currently sets every cell. A `level-data` array of
30x4 bytes per level and a `level` counter would let `init-level` build
different shapes (gaps, fortresses, asymmetric layouts) and ramp difficulty.
Touching: `bricks.fs` (read from a layout instead of `grid-clear 1`),
`game.fs` (advance level on `handle-cleared`).

### Multi-hit bricks
Each brick currently dies in one hit. A second byte per cell — or stealing a
nibble of the existing one — could store a hit-points value, with the brick
attribute changing on each hit before erasure. Touching: `bricks.fs` only.

### Power-ups
Falling tokens released by some bricks: paddle-grow, paddle-shrink, slow-ball,
multi-ball, extra-life. Each is an 8x8 sprite that descends from the brick's
column at a fixed rate; collision with the paddle (same x-overlap test as the
ball) applies the effect. Adds a `powerups.fs` module and a small slot-table
of active descenders.

### Variable ball speed
`|dy|` is hard-coded to 2. Allowing |dy| ∈ {1, 2, 3} (matching dx) would give
genuinely different speeds — useful as a power-up or a level ramp. Mind that
the smart-restore logic and `ball-max-y` analysis assume `|dy| = 2`; verify
that ball-y still lands cleanly on `paddle-top-px - 8` before it ever paints
past row 21 with any new dy.

### Game-over screen and restart
`game-loop` exits via `dead?`, the program halts. A "GAME OVER — press space"
prompt would loop until input then re-enter `arkanoid`. Touching: `game.fs`.

### Pause
A toggle on, say, the `H` key that suspends `ball-physics` (and possibly
`paddle-step`) without exiting `game-loop`. Easy to add — keep `wait-frame`
and the renders running so the screen stays alive but the simulation freezes.

## Visual polish

### Sound on bounce / brick / death
`sound.fs` is part of the stdlib but unused here. A short beep on each
event would add a lot. Touching: `ball.fs` (call into `sound.fs` at each
bounce / brick / floor), `score.fs` (death sound).

### Score-pop animation
When a brick dies, briefly show "+10" rising from the brick before fading.
A handful of slot-tracked particles updated each frame.

### Paddle colour flash on hit
`bounce-paddle` could write a brighter attribute to the paddle row for one
frame to signal contact. Trivial: one extra `row-attrs!` call, then revert
on the next frame.

### Ball trail
Optional: keep one or two prior ball positions and draw them dimmer (paper
attribute change). Currently *removed* trails are the goal — but a deliberate
short trail can read as motion blur. Trade-off: more cells touched per frame.

## Performance / engine

### Skip restore when ball stays in same pixel position
Currently `ball-moved?` is the only restore predicate, and it is essentially
"always true" during play. That's fine, but if a future feature pauses the
ball (sticky paddle, freeze power-up), `restore-ball-bg` should noop. Already
correct as written — flagging here so the predicate isn't tightened back to
a cell-only check by mistake.

### Tighter horizontal restore footprint
`restore-old-cells` always touches two cells horizontally because `blit8x` is
16 pixels wide. When the ball's `x mod 8 = 0`, the right half of that window
is all zeros — no pixels actually written there — so the right cell of the
restore is wasted. A `ball-x-aligned?` check symmetric to `ball-y-aligned?`
would let restore drop one cell when both axes are aligned. Saves at most
`8 / 4` of a cell's restore cost on aligned frames; small but free.

### Cache `paddle-left-px`
`paddle-left-px` recomputes `paddle-col @ 8 *` on every call. `bounce-paddle`,
`ball-overlaps-paddle-x?`, and `paddle-bounce-dx` each call it. Storing the
current pixel position in a variable updated by `paddle-step` would cut a
multiplication per access at the cost of one extra store per move.

### Cache brick-row attributes
`row-attr` does an `@` and a `+` each time. The 4 attributes could live in
4 named constants for slightly faster access during `draw-bricks-row`.

### Direct HUD writes instead of `emit`
`emit` goes through the ROM glyph copier (~600 t-states per character).
Writing 4 digits costs ~2.4k t-states per HUD update. Pre-computing the
character cell address and copying the 8 glyph bytes directly with `move`
would cut that roughly in half. Touching: `game.fs` `emit-3digits` /
`emit-digit`.

### Coalesce `draw-all-bricks`
`draw-all-bricks` is called at level start and on `handle-cleared`. It
currently does 120 separate `blit8c` calls. A row-major loop that writes
a whole 30-cell row of pixel bytes and a 30-cell row of attributes in two
tight inner loops would be markedly faster. Cosmetic during a clear/reload
moment, so low priority.

## Code structure

### Dead-code removal
- `erase-ball` (ball.fs) — superseded by cell-level restore in game.fs.
- `erase-paddle-at`, `erase-paddle` (paddle.fs) — superseded by
  `erase-paddle-trail`.
- `ball-step` (ball.fs) — `game-step` calls `ball-physics` and `ball-paint`
  separately so the rendering and physics live at opposite ends of the frame.
- `cell-is-wall?`, `bricks-screen-row`, `bricks-screen-col` — built but never
  called; either inline-document why they're kept or delete.

### Name collision: two `ball-center-x`
`bricks.fs` defines `ball-center-x ( bx -- cx )` (consumes a stack value),
`ball.fs` inlines `ball-x @ 4 +` to avoid redefining it. Pick one shape and
rename the other (`ball-center-x` is fine for the value-on-stack form;
`ball-cx` could be the no-arg accessor). Builder warns but compiles.

### Move HUD code into `score.fs`
`hud-print-score`, `hud-print-lives`, `hud-print-labels`, `draw-hud`,
`maybe-draw-hud` all live in `game.fs` but are conceptually score/lives UI.
Moving them into `score.fs` would shrink `game.fs` and keep the HUD's three
files (state, render, dirty-bit) co-located.

### Consolidate ball-position snapshots
There's `ball-save-pos` (writes ox/oy) called from `ball-paint`,
`ball-reset`, `init-level`, `handle-ball-lost`, `handle-cleared`. It would
be cleaner if `ball-reset` always invoked `ball-save-pos` itself, so the
caller doesn't need both lines.

### Split `init-level`
`init-level` does brick init, wall draw, paddle reset, ball reset, paint,
HUD setup. Split into `level-load` (bricks + walls), `entities-reset`
(paddle + ball), `paint-fresh-frame` (initial draws + HUD).

## Test coverage

### Brick collision determinism
There's no test that proves a brick directly above a moving ball gets hit.
Add a test that primes ball state to a known position and y-direction,
runs one physics step, and asserts the brick at the ball's centre is dead.

### `bounce-paddle` zone table
`paddle-bounce-dx` is purely arithmetic; a parametrised pytest that loads
the image, sets `ball-x` and `paddle-col` to a table of values, runs
`bounce-paddle` directly (e.g. via a tiny test-only Forth word), and
asserts the resulting `ball-dx` would lock the zones in.

### Level-cleared path
No test currently covers the brick-count-zero branch in `handle-cleared`
(level wraps). A test that scripts the ball or pre-wipes the grid would
exercise the ball-reset + draw-all-bricks code path.

### Frame-cost guard rail
A test that asserts the per-frame body stays under, say, 50k t-states would
catch performance regressions that this codebase has otherwise had to chase
by hand.
