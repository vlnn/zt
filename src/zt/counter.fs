\ counter.fs — M3 demo
\ Cycles through border colors 0-255 forever.
\ Equivalent to the hand-built demo in image.py.

: main  0 begin dup border 1+ again ;
