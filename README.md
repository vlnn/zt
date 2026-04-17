M7 — Symbol map and debugging.

Replaces in your tree:
  src/zt/compiler.py
  src/zt/cli.py

New:
  src/zt/debug.py    SourceEntry
  src/zt/mapfile.py  Fuse + ZEsarUX map writers
  src/zt/sld.py      sjasmplus-style SLD writer
  src/zt/fsym.py     JSON host-dictionary writer/loader
  src/zt/inspect.py  raw decompiler

CLI surface:
  zt build src.fs -o out.sna [--map PATH] [--map-format fuse|zesarux]
                             [--sld PATH] [--fsym PATH]
  zt inspect --symbols out.fsym

Byte-identical .sna guaranteed by tests/test_m7_cli.py::TestImageUnchangedByDebugFlags
and tests/test_m7_step1.py::TestImageUnchanged.
