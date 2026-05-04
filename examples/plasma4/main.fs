\ Multi-file plasma entry point.  Doubles as a smoke test for require
\ deduplication: `app/plasma.fs` requires `../lib/math.fs`, then
\ `../lib/screen.fs`, which in turn requires `math.fs` from the same
\ lib directory.  The resolver canonicalises both paths to the same
\ file and loads it once.

require app/plasma.fs

: main
    0 0 cls
    animate ;
