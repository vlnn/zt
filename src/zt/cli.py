from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zt.compiler import Compiler, CompileError
from zt.fsym import load_fsym, write_fsym
from zt.inspect import decompile
from zt.mapfile import FUSE, ZESARUX, write_map
from zt.sld import write_sld
from zt.sna import build_sna


SUPPORTED_FORMATS = ("sna", "bin")
FORMAT_BY_EXTENSION = {".sna": "sna", ".bin": "bin", ".tap": "tap"}


def main() -> None:
    parser = argparse.ArgumentParser(prog="zt", description="Z80 Forth cross-compiler")
    sub = parser.add_subparsers(dest="command")
    _register_build(sub)
    _register_inspect(sub)

    args = parser.parse_args()
    if args.command == "build":
        _do_build(args)
        return
    if args.command == "inspect":
        _do_inspect(args)
        return
    parser.print_help()


def _register_build(sub: argparse._SubParsersAction) -> None:
    build = sub.add_parser("build", help="compile Forth source to Spectrum snapshot")
    build.add_argument("source", type=Path, help=".fs source file")
    build.add_argument("-o", "--output", type=Path, required=True, help="output file")
    build.add_argument("--format", choices=SUPPORTED_FORMATS, default=None,
                       help="output format (auto-detected from extension if omitted)")
    build.add_argument("--origin", type=lambda s: int(s, 0), default=0x8000)
    build.add_argument("--dstack", type=lambda s: int(s, 0), default=0xFF00)
    build.add_argument("--rstack", type=lambda s: int(s, 0), default=0xFE00)
    build.add_argument("--border", type=int, default=7, choices=range(8))
    build.add_argument("--include-dir", action="append", type=Path, default=[],
                       dest="include_dirs", metavar="PATH",
                       help="additional search path for INCLUDE/REQUIRE (repeatable)")
    build.add_argument("--map", type=Path, default=None, dest="map_path",
                       metavar="PATH", help="write symbol map to PATH")
    build.add_argument("--map-format", choices=[FUSE, ZESARUX], default=None,
                       dest="map_format",
                       help="force map format (default: auto from extension)")
    build.add_argument("--sld", type=Path, default=None, dest="sld_path",
                       metavar="PATH", help="write sjasmplus-style SLD to PATH")
    build.add_argument("--fsym", type=Path, default=None, dest="fsym_path",
                       metavar="PATH", help="write JSON host dictionary to PATH")
    build.add_argument("--stdlib", dest="stdlib", action="store_true", default=True,
                       help="include bundled stdlib/core.fs (default)")
    build.add_argument("--no-stdlib", dest="stdlib", action="store_false",
                       help="skip bundled stdlib/core.fs")


def _register_inspect(sub: argparse._SubParsersAction) -> None:
    ins = sub.add_parser("inspect", help="decompile colon words from an fsym file")
    ins.add_argument("--symbols", type=Path, required=True, dest="symbols",
                     metavar="PATH", help="path to .fsym JSON file")


def _do_build(args: argparse.Namespace) -> None:
    if not args.source.exists():
        print(f"error: {args.source} not found", file=sys.stderr)
        sys.exit(1)

    fmt = args.format or _detect_format(args.output)
    if fmt not in SUPPORTED_FORMATS:
        print(f"error: unsupported output format '{fmt}'", file=sys.stderr)
        sys.exit(1)

    try:
        compiler = _build_compiler(args)
        image = compiler.build()
    except CompileError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    _write_output(image, args, compiler, fmt)
    _write_debug_artifacts(compiler, args)
    _print_summary(args.source, args.output, image, compiler, fmt)


def _write_debug_artifacts(compiler: Compiler, args: argparse.Namespace) -> None:
    if args.map_path:
        write_map(compiler, args.map_path, fmt=args.map_format)
    if args.sld_path:
        write_sld(compiler, args.sld_path)
    if args.fsym_path:
        write_fsym(compiler, args.fsym_path)


def _do_inspect(args: argparse.Namespace) -> None:
    if not args.symbols.exists():
        print(f"error: {args.symbols} not found", file=sys.stderr)
        sys.exit(1)
    fsym = load_fsym(args.symbols)
    sys.stdout.write(decompile(fsym))


def _build_compiler(args: argparse.Namespace) -> Compiler:
    c = Compiler(
        origin=args.origin,
        data_stack_top=args.dstack,
        return_stack_top=args.rstack,
        include_dirs=args.include_dirs,
    )
    if args.stdlib:
        c.include_stdlib()
    c.compile_source(args.source.read_text(), source=str(args.source))
    c.compile_main_call()
    return c


def _detect_format(output_path: Path) -> str:
    ext = output_path.suffix.lower()
    fmt = FORMAT_BY_EXTENSION.get(ext)
    if fmt is None:
        raise SystemExit(
            f"error: cannot determine format from extension '{ext}'; "
            f"use --format {'|'.join(SUPPORTED_FORMATS)}"
        )
    if fmt == "tap":
        raise SystemExit("error: .tap output is not yet implemented (see M8)")
    return fmt


def _write_output(image: bytes, args: argparse.Namespace,
                  compiler: Compiler, fmt: str) -> None:
    if fmt == "sna":
        sna = build_sna(image, args.origin, args.dstack,
                        border=args.border,
                        entry=compiler.words["_start"].address)
        args.output.write_bytes(sna)
        return
    if fmt == "bin":
        args.output.write_bytes(image)
        return
    raise AssertionError(f"unreachable: format {fmt}")


def _print_summary(source: Path, output: Path, image: bytes,
                   compiler: Compiler, fmt: str) -> None:
    word_count = sum(1 for w in compiler.words.values() if w.kind == "colon")
    out_size = output.stat().st_size
    print(f"{source} -> {output} [{fmt}] "
          f"({len(image)} bytes code, {word_count} words, {out_size} bytes output)")


if __name__ == "__main__":
    main()
