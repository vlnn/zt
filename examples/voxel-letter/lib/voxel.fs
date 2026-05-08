\ lib/voxel.fs — basis-baking for the incremental two-axis renderer.
\
\ For a cz = 0 letter slice the projection is:
\   buffer_x = cx · cos(yaw)   + buf-half
\   buffer_y = cy · cos(pitch) + buf-half
\
\ Voxel cells sit at half-integer offsets {-3.5, -2.5, ..., +3.5} so the
\ 8-cell cube projects symmetrically into 8 contiguous pixels [0, 7]
\ regardless of rotation angle.  This lets the back-buffer be one 8-byte
\ block (1 char cell) instead of four 8-byte quadrants.
\
\ All quantities are 8.8 fixed point.

require ../lib/sin64.fs

\ Buffer centre at 3.5 in 8.8 fp = 896.
896 constant buf-half-fp

variable frame-step-x
variable frame-step-y
variable frame-base-x
variable frame-base-y

: bake-frame  ( yaw pitch -- )
    cos@                                       frame-step-y !
    cos@                                       frame-step-x !
    frame-step-x @  -7 *  2/   buf-half-fp +   frame-base-x !
    frame-step-y @  -7 *  2/   buf-half-fp +   frame-base-y ! ;
