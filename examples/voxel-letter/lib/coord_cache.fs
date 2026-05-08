\ lib/coord_cache.fs — per-frame projection caches.
\
\ Pre-computed once per frame in render.fs::bake-coords; consumed by
\ the :::-Z80 render_row.fs.  Both x-cache and y-cache hold one byte
\ per cube row/col (buffer-relative coords in [0, 15]).

create x-cache  8 allot
create y-cache  8 allot
