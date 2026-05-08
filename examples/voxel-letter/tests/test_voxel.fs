include test-lib.fs
require ../lib/voxel.fs

\ ── bake-frame seeds the per-frame basis correctly ────────────────────
\ At yaw=0 (cos=1.0 = 256 in 8.8): step-x = 256, base-x = -3.5·256 + 3.5·256
\ = 0.  First voxel cx=-3.5 projects to buffer-x=0.

: test-step-x-yaw-0       0 0 bake-frame  frame-step-x @  256  assert-eq ;
: test-step-y-pitch-0     0 0 bake-frame  frame-step-y @  256  assert-eq ;
: test-base-x-yaw-0       0 0 bake-frame  frame-base-x @  0    assert-eq ;
: test-base-y-pitch-0     0 0 bake-frame  frame-base-y @  0    assert-eq ;

\ ── yaw=16 (90°, cos=0): step is 0, base is buffer centre (3.5 fp) ───

: test-step-x-yaw-90      16 0 bake-frame  frame-step-x @  0    assert-eq ;
: test-base-x-yaw-90      16 0 bake-frame  frame-base-x @  896  assert-eq ;

\ ── yaw=32 (180°, cos=-1): step negated, base mirrored ───────────────
\ base-x = -3.5·-256 + 896 = 896 + 896 = 1792 (= 7.0 in fp)

: test-step-x-yaw-180     32 0 bake-frame  frame-step-x @  -256 assert-eq ;
: test-base-x-yaw-180     32 0 bake-frame  frame-base-x @  1792 assert-eq ;

\ ── pitch axis behaves the same way using the same machinery ─────────

: test-step-y-pitch-90    0 16 bake-frame  frame-step-y @  0    assert-eq ;
: test-step-y-pitch-180   0 32 bake-frame  frame-step-y @  -256 assert-eq ;

\ ── walking 7 steps from base-x lands on the last voxel's pixel ──────
\ At yaw=0:   walk 0 + 7·256 = 1792 fp = 7 int (last voxel cx=+3.5)
\ At yaw=180: walk 1792 + 7·-256 = 0 fp = 0 int (last voxel mirrored)

: walk-x-7-times  ( -- final )
    frame-base-x @
    7 0 do  frame-step-x @ +  loop ;

: test-walk-yaw-0-final
    0 0 bake-frame
    walk-x-7-times  fixed>int  7 assert-eq ;

: test-walk-yaw-180-final
    32 0 bake-frame
    walk-x-7-times  fixed>int  0 assert-eq ;
