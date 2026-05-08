include test-lib.fs
require ../lib/sin64.fs

\ key fixed-point reference values:
\   sin(0°)   = 0
\   sin(90°)  = 256   (1.0 in 8.8)
\   sin(180°) = 0
\   sin(270°) = -256
\   cos(0°)   = 256
\   cos(90°)  = 0

: test-sin-zero            0  sin@   0    assert-eq ;
: test-sin-quarter         16 sin@   256  assert-eq ;
: test-sin-half            32 sin@   0    assert-eq ;
: test-sin-three-quarter   48 sin@   -256 assert-eq ;

: test-cos-zero            0  cos@   256  assert-eq ;
: test-cos-quarter         16 cos@   0    assert-eq ;
: test-cos-half            32 cos@   -256 assert-eq ;
: test-cos-three-quarter   48 cos@   0    assert-eq ;

\ wrap-around at 64 = 0
: test-sin-wraps-64        64 sin@   0    assert-eq ;
: test-sin-wraps-65        65 sin@   25   assert-eq ;
: test-sin-wraps-negative  -1 sin@   -25  assert-eq ;

\ a sample mid-arc value: sin(45°) = sin(8/64 turn) ≈ 0.707
\ in 8.8: 0.707 × 256 ≈ 181
: test-sin-eighth          8  sin@   181  assert-eq ;
: test-cos-eighth          8  cos@   181  assert-eq ;

\ Pythagorean check at a few angles: sin² + cos² ≈ 1 in 8.8 = 256.
\ f* shifts each operand right by 4 before multiplying, so fractional
\ values lose ~6 bits of precision; tolerate ±20.
: test-pythagoras-zero
    0 sin@ dup f*  0 cos@ dup f*  +
    256 - abs  20 <  assert-true ;

: test-pythagoras-eighth
    8 sin@ dup f*  8 cos@ dup f*  +
    256 - abs  20 <  assert-true ;
