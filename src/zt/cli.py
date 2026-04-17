from __future__ import annotations

import argparse
from pathlib import Path

from zt.image import build_image
from zt.sna import build_sna


def main() -> None:
    parser = argparse.ArgumentParser(prog="zt", description="Z80 Forth cross-compiler")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="build a Spectrum snapshot")
    build.add_argument("output", type=Path)
    build.add_argument("--origin", type=lambda s: int(s, 0), default=0x8000)
    build.add_argument("--dstack", type=lambda s: int(s, 0), default=0xFF00)
    build.add_argument("--rstack", type=lambda s: int(s, 0), default=0xFE00)

    args = parser.parse_args()

    if args.command == "build":
        code = build_image(args.origin, args.dstack, args.rstack)
        sna = build_sna(code, args.origin, args.dstack, args.border)
        args.output.write_bytes(sna)
        print(f"wrote {len(sna)} bytes to {args.output} "
              f"(code {len(code)} bytes at {args.origin:#06x})")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
