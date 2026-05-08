\ lib/sin64.fs — 64-entry signed sine table in 8.8 fixed-point.
\
\ angular resolution: 360°/64 = 5.625°.  At max voxel radius √3·3.5 ≈ 6.06,
\ that's 0.59 px/step tangential — finer than 1-pixel screen quantisation
\ would distinguish, but smooth enough to read as rotation.
\
\ values: round(sin(2π·i/64) · 256), so they're already 8.8 fixed and feed
\ straight into f* without rescaling.

require array.fs
require fixed.fs

w: sine64
        0    25    50    74    98   121   142   162
      181   198   213   226   237   245   251   255
      256   255   251   245   237   226   213   198
      181   162   142   121    98    74    50    25
        0   -25   -50   -74   -98  -121  -142  -162
     -181  -198  -213  -226  -237  -245  -251  -255
     -256  -255  -251  -245  -237  -226  -213  -198
     -181  -162  -142  -121   -98   -74   -50   -25
;

\ wrap an angle (any int) into [0, 63]
: wrap64    ( angle -- index )   63 and ;

\ sin in 8.8 fixed; angle in 64ths of a turn, any integer
: sin@      ( angle -- sin-fix ) wrap64 sine64 swap a-word@ ;

\ cos lags sin by 90° = 16 steps
: cos@      ( angle -- cos-fix ) 16 + sin@ ;
