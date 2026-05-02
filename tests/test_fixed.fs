include test-lib.fs
include fixed.fs

: test-fixed-one-constant       fixed-one 256 assert-eq ;
: test-fixed-half-constant      fixed-half 128 assert-eq ;

: test-to-fixed-zero            0 >fixed 0 assert-eq ;
: test-to-fixed-one             1 >fixed 256 assert-eq ;
: test-to-fixed-five            5 >fixed 1280 assert-eq ;
: test-to-fixed-negative-one    -1 >fixed -256 assert-eq ;
: test-to-fixed-negative-three  -3 >fixed -768 assert-eq ;
: test-to-fixed-max             127 >fixed 32512 assert-eq ;
: test-to-fixed-min             -128 >fixed -32768 assert-eq ;

: test-from-fixed-zero          0 fixed>int 0 assert-eq ;
: test-from-fixed-exact-one     256 fixed>int 1 assert-eq ;
: test-from-fixed-exact-five    1280 fixed>int 5 assert-eq ;
: test-from-fixed-truncates-pos 384 fixed>int 1 assert-eq ;
: test-from-fixed-tiny-pos      1 fixed>int 0 assert-eq ;
: test-from-fixed-just-under    255 fixed>int 0 assert-eq ;
: test-from-fixed-exact-neg     -256 fixed>int -1 assert-eq ;
: test-from-fixed-truncates-neg -384 fixed>int -1 assert-eq ;
: test-from-fixed-tiny-neg      -1 fixed>int 0 assert-eq ;
: test-from-fixed-just-above    -255 fixed>int 0 assert-eq ;

: test-roundtrip-five           5 >fixed fixed>int 5 assert-eq ;
: test-roundtrip-negative-five  -5 >fixed fixed>int -5 assert-eq ;
: test-roundtrip-zero           0 >fixed fixed>int 0 assert-eq ;

: test-add-natively             1 >fixed 2 >fixed +  3 >fixed assert-eq ;
: test-sub-natively             5 >fixed 2 >fixed -  3 >fixed assert-eq ;
: test-mul-by-int               3 >fixed 4 *  12 >fixed assert-eq ;
: test-mul-by-int-half          fixed-half 4 *  2 >fixed assert-eq ;
: test-div-by-int               6 >fixed 4 /  fixed-half 3 * assert-eq ;

: test-fmul-positive            3 >fixed 4 >fixed f*  12 >fixed assert-eq ;
: test-fmul-fractional          3 >fixed fixed-half f*  fixed-half 3 * assert-eq ;
: test-fmul-by-half             8 >fixed fixed-half f*  4 >fixed assert-eq ;
: test-fmul-negative            3 >fixed -4 >fixed f*  -12 >fixed assert-eq ;
: test-fmul-both-negative       -3 >fixed -4 >fixed f*  12 >fixed assert-eq ;
: test-fmul-zero                42 >fixed 0 f*  0 assert-eq ;

: test-frac-zero                0 u-frac 0 assert-eq ;
: test-frac-half                fixed-half u-frac 50 assert-eq ;
: test-frac-quarter             64 u-frac 25 assert-eq ;
: test-frac-eighth              32 u-frac 12 assert-eq ;
: test-frac-one-clean           fixed-one u-frac 0 assert-eq ;
