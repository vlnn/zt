\ Multi-file plasma entry point.
\
\ Include graph:
\    main.fs
\      require app/plasma.fs
\        require ../lib/math.fs     <- canonical path
\        require ../lib/screen.fs
\          require math.fs          <- same canonical path (dedup)

require app/plasma.fs

: main
    0 0 cls
    animate ;
