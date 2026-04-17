from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zt.compiler import Compiler, CompileError
from zt.sna import build_sna


def main() -> None:
    parser = argparse.ArgumentParser(prog="zt", description="Z80 Forth cross-compiler")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build", help="compile Forth source to Spectrum snapshot")
    build.add_argument("source", type=Path, help=".fs source file")
    build.add_argument("-o", "--output", type=Path, required=True, help="output .sna file")
    build.add_argument("--origin", type=lambda s: int(s, 0), default=0x8000)
    build.add_argument("--dstack", type=lambda s: int(s, 0), default=0xFF00)
    build.add_argument("--rstack", type=lambda s: int(s, 0), default=0xFE00)
    build.add_argument("--border", type=int, default=7, choices=range(8))
    build.add_argument("--stdlib", dest="stdlib", action="store_true", default=True,
                       help="include bundled stdlib/core.fs (default)")
    build.add_argument("--no-stdlib", dest="stdlib", action="store_false",
                       help="skip bundled stdlib/core.fs")

    args = parser.parse_args()

    if args.command == "build":
        _do_build(args)
    else:
        parser.print_help()


def _do_build(args: argparse.Namespace) -> None:
    source_path = args.source
    if not source_path.exists():
        print(f"error: {source_path} not found", file=sys.stderr)
        sys.exit(1)

    source_text = source_path.read_text()

    try:
        c = Compiler(
            origin=args.origin,
            data_stack_top=args.dstack,
            return_stack_top=args.rstack,
        )
        if args.stdlib:
            c.include_stdlib()
        c.compile_source(source_text, source=str(source_path))
        c.compile_main_call()
        image = c.build()
    except CompileError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    sna = build_sna(image, args.origin, args.dstack,
                    border=args.border,
                    entry=c.words["_start"].address)
    args.output.write_bytes(sna)

    word_count = sum(1 for w in c.words.values() if w.kind == "colon")
    print(f"{source_path} -> {args.output} "
          f"({len(image)} bytes code, {word_count} words, {len(sna)} bytes snapshot)")


if __name__ == "__main__":
    main()
