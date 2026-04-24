"""
`zt` command-line entry point. Parses the `build` / `inspect` / `test` / `profile` subcommands and dispatches them to the compiler, image loader and artifact writers.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zt.compile.compiler import Compiler, CompileError
from zt.inspect.fsym import load_fsym, write_fsym
from zt.inspect.decompile import decompile
from zt.format.mapfile import FUSE, ZESARUX, write_map
from zt.cli.profile import args_from_namespace, register_profile, run_profile_command
from zt.format.sld import write_sld
from zt.format.sna import BANK_SIZE, build_sna, build_sna_128
from zt.format.z80 import build_z80_v3


SUPPORTED_FORMATS = ("sna", "z80", "bin")
FORMAT_BY_EXTENSION = {".sna": "sna", ".z80": "z80", ".bin": "bin", ".tap": "tap"}


def main() -> None:
    parser = argparse.ArgumentParser(prog="zt", description="Z80 Forth cross-compiler")
    sub = parser.add_subparsers(dest="command")
    _register_build(sub)
    _register_inspect(sub)
    _register_test(sub)
    register_profile(sub)

    args = parser.parse_args()
    if args.command == "build":
        _do_build(args)
        return
    if args.command == "inspect":
        _do_inspect(args)
        return
    if args.command == "test":
        _do_test(args)
        return
    if args.command == "profile":
        sys.exit(run_profile_command(args_from_namespace(args), sys.stdout, sys.stderr))
    parser.print_help()


def _register_build(sub: argparse._SubParsersAction) -> None:
    build = sub.add_parser("build", help="compile Forth source to Spectrum snapshot")
    build.add_argument("source", type=Path, help=".fs source file")
    build.add_argument("-o", "--output", type=Path, required=True, help="output file")
    build.add_argument("--format", choices=SUPPORTED_FORMATS, default=None,
                       help="output format (auto-detected from extension if omitted)")
    build.add_argument("--origin", type=lambda s: int(s, 0), default=0x8000)
    build.add_argument("--dstack", type=lambda s: int(s, 0), default=None,
                       help="data stack top (48k default $FF00, 128k default $BF00)")
    build.add_argument("--rstack", type=lambda s: int(s, 0), default=None,
                       help="return stack top (48k default $FE00, 128k default $BE00)")
    build.add_argument("--target", choices=("48k", "128k"), default="48k",
                       help="target model (default: 48k)")
    build.add_argument("--paged-bank", type=lambda s: int(s, 0), default=None,
                       dest="paged_bank",
                       help="initial bank at $C000 for 128k target (0..7, default 7 — ensures display wiring is ready on Pentagon/ZX128 at load time)")
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
    build.add_argument("--no-optimize", dest="optimize", action="store_false",
                       default=True, help="disable peephole optimizer")
    build.add_argument("--inline-next", dest="inline_next", action="store_true",
                       default=True,
                       help="inline the NEXT dispatch body into each primitive "
                            "(default; ~10%% speedup, ~500 bytes larger image)")
    build.add_argument("--no-inline-next", dest="inline_next",
                       action="store_false",
                       help="do not inline the NEXT dispatch body")
    build.add_argument("--inline-primitives", dest="inline_primitives",
                       action="store_true", default=True,
                       help="inline pure-primitive colons by replacing "
                            "the CALL DOCOL prologue with pasted primitive bytes "
                            "(default)")
    build.add_argument("--no-inline-primitives", dest="inline_primitives",
                       action="store_false",
                       help="do not inline pure-primitive colons")
    build.add_argument("--profile", dest="profile", action="store_true", default=False,
                       help="run the built image in the simulator and write a profile report")
    build.add_argument("--profile-output", type=Path, default=None, dest="profile_output",
                       metavar="PATH",
                       help="override profile report path (default: <output>.prof)")
    build.add_argument("--profile-ticks", type=int, default=1_000_000,
                       dest="profile_ticks", metavar="N",
                       help="tick budget for the profile run (default: 1_000_000)")


def _register_inspect(sub: argparse._SubParsersAction) -> None:
    ins = sub.add_parser("inspect", help="decompile colon words from an fsym file")
    ins.add_argument("--symbols", type=Path, required=True, dest="symbols",
                     metavar="PATH", help="path to .fsym JSON file")
    ins.add_argument("--image", type=Path, default=None, dest="image",
                     metavar="PATH", help="raw image file (e.g. .bin) for "
                                          "reconstructing string literals")


PAGED_SLOT_START = 0xC000
DEFAULT_DSTACK_48K = 0xFF00
DEFAULT_RSTACK_48K = 0xFE00
DEFAULT_DSTACK_128K = 0xBF00
DEFAULT_RSTACK_128K = 0xBE00


def _resolve_stack_defaults(args: argparse.Namespace) -> None:
    if args.dstack is None:
        args.dstack = DEFAULT_DSTACK_128K if args.target == "128k" else DEFAULT_DSTACK_48K
    if args.rstack is None:
        args.rstack = DEFAULT_RSTACK_128K if args.target == "128k" else DEFAULT_RSTACK_48K


def _validate_128k_config(args: argparse.Namespace) -> None:
    if args.paged_bank is None:
        args.paged_bank = 7
    if not (0 <= args.paged_bank <= 7):
        print(
            f"error: --paged-bank {args.paged_bank} must be in range 0..7",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.dstack >= PAGED_SLOT_START:
        print(
            f"error: --dstack {args.dstack:#06x} lands in the paged slot "
            f"(${PAGED_SLOT_START:04X}+); 128k stacks must live in bank 2",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.rstack >= PAGED_SLOT_START:
        print(
            f"error: --rstack {args.rstack:#06x} lands in the paged slot "
            f"(${PAGED_SLOT_START:04X}+); 128k stacks must live in bank 2",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.origin >= PAGED_SLOT_START:
        print(
            f"error: --origin {args.origin:#06x} lands in the paged slot; "
            f"128k code must live in bank 2 or bank 5",
            file=sys.stderr,
        )
        sys.exit(1)


def _validate_48k_config(args: argparse.Namespace) -> None:
    if args.paged_bank is not None:
        print(
            "error: --paged-bank requires --target 128k",
            file=sys.stderr,
        )
        sys.exit(1)


def _do_build(args: argparse.Namespace) -> None:
    if not args.source.exists():
        print(f"error: {args.source} not found", file=sys.stderr)
        sys.exit(1)

    fmt = args.format or _detect_format(args.output)
    if fmt not in SUPPORTED_FORMATS:
        print(f"error: unsupported output format '{fmt}'", file=sys.stderr)
        sys.exit(1)

    _resolve_stack_defaults(args)
    if args.target == "128k":
        _validate_128k_config(args)
    else:
        _validate_48k_config(args)

    try:
        compiler = _build_compiler(args)
        image = compiler.build()
    except CompileError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    _write_output(image, args, compiler, fmt)
    _write_debug_artifacts(compiler, args)
    _write_profile(compiler, image, args)
    _emit_warnings(compiler)
    _print_summary(args.source, args.output, image, compiler, fmt)


def _emit_warnings(compiler: Compiler) -> None:
    for msg in compiler.warnings:
        print(msg, file=sys.stderr)


def _write_debug_artifacts(compiler: Compiler, args: argparse.Namespace) -> None:
    if args.map_path:
        write_map(compiler, args.map_path, fmt=args.map_format)
    if args.sld_path:
        write_sld(compiler, args.sld_path)
    if args.fsym_path:
        write_fsym(compiler, args.fsym_path)


def _write_profile(compiler: Compiler, image: bytes, args: argparse.Namespace) -> None:
    if not args.profile:
        return
    from zt.profile.core import Profiler, build_word_ranges, format_report
    from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80

    ranges = build_word_ranges(
        {name: w.address for name, w in compiler.words.items()},
        code_end=compiler.origin + len(image),
    )
    profiler = Profiler(ranges)

    m = Z80()
    m.load(compiler.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = compiler.words["_start"].address
    m.run(max_ticks=args.profile_ticks, profiler=profiler)

    path = args.profile_output or args.output.with_suffix(".prof")
    path.write_text(format_report(profiler.report()) + "\n")


def _do_inspect(args: argparse.Namespace) -> None:
    if not args.symbols.exists():
        print(f"error: {args.symbols} not found", file=sys.stderr)
        sys.exit(1)
    image = _load_image(args)
    fsym = load_fsym(args.symbols)
    sys.stdout.write(decompile(fsym, image=image))


def _load_image(args: argparse.Namespace) -> bytes | None:
    if args.image is None:
        return None
    if not args.image.exists():
        print(f"error: {args.image} not found", file=sys.stderr)
        sys.exit(1)
    return args.image.read_bytes()


def _build_compiler(args: argparse.Namespace) -> Compiler:
    c = Compiler(
        origin=args.origin,
        data_stack_top=args.dstack,
        return_stack_top=args.rstack,
        include_dirs=args.include_dirs,
        optimize=args.optimize,
        inline_next=args.inline_next,
        inline_primitives=args.inline_primitives,
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


def _image_to_banks(image: bytes, origin: int) -> dict[int, bytes]:
    if 0x4000 <= origin < 0x8000:
        bank_id, base = 5, 0x4000
    elif 0x8000 <= origin < 0xC000:
        bank_id, base = 2, 0x8000
    else:
        raise ValueError(
            f"origin {origin:#06x} must live in bank 5 ($4000-$7FFF) "
            f"or bank 2 ($8000-$BFFF) for --target 128k"
        )
    offset = origin - base
    if offset + len(image) > BANK_SIZE:
        raise ValueError(
            f"image of {len(image)} bytes at origin {origin:#06x} overflows bank "
            f"{bank_id}; cross-bank code placement is not yet supported"
        )
    return {bank_id: bytes(offset) + image}


def _write_output(image: bytes, args: argparse.Namespace,
                  compiler: Compiler, fmt: str) -> None:
    if fmt == "z80" and args.target == "48k":
        print(
            "error: --format z80 requires --target 128k "
            "(48k .z80 output is not supported)",
            file=sys.stderr,
        )
        sys.exit(1)
    if fmt == "z80":
        try:
            banks = _image_to_banks(image, args.origin)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        banks.update(compiler.banks())
        z80 = build_z80_v3(
            banks,
            entry=compiler.words["_start"].address,
            paged_bank=args.paged_bank,
            data_stack_top=args.dstack,
            border=args.border,
        )
        args.output.write_bytes(z80)
        return
    if fmt == "sna" and args.target == "128k":
        try:
            banks = _image_to_banks(image, args.origin)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        banks.update(compiler.banks())
        sna = build_sna_128(
            banks,
            entry=compiler.words["_start"].address,
            paged_bank=args.paged_bank,
            data_stack_top=args.dstack,
            border=args.border,
        )
        args.output.write_bytes(sna)
        return
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


def _register_test(sub: argparse._SubParsersAction) -> None:
    t = sub.add_parser("test", help="run Forth test files")
    t.add_argument("specs", nargs="*", default=["."],
                   help="files, directories, or FILE::WORD specs (default: cwd)")
    t.add_argument("-k", dest="filter", default=None, metavar="PATTERN",
                   help="only run tests whose name contains PATTERN")
    t.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                   default=False, help="one line per test with PASS/FAIL")
    t.add_argument("-x", "--exitfirst", dest="exitfirst", action="store_true",
                   default=False, help="stop after the first failure")
    t.add_argument("--max-ticks", type=int, default=1_000_000, dest="max_ticks",
                   metavar="N", help="per-test tick budget (default: 1_000_000)")


def _do_test(args: argparse.Namespace) -> None:
    from zt.test_runner import TestDiscoveryError, TestEvent, run_tests

    def on_result(event: TestEvent) -> None:
        if event.result.failed:
            _report_fail(event, args.verbose)
        else:
            _report_pass(event, args.verbose)

    try:
        summary = run_tests(
            args.specs,
            keyword=args.filter,
            stop_on_first_failure=args.exitfirst,
            on_result=on_result,
            max_ticks=args.max_ticks,
        )
    except TestDiscoveryError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    _print_failures(summary.failures)
    _print_test_summary(summary.passed, summary.failures)
    sys.exit(0 if summary.success else 1)


def _report_pass(event, verbose: bool) -> None:
    if verbose:
        print(f"{event.path}::{event.word} PASSED")
    else:
        sys.stdout.write(".")
        sys.stdout.flush()


def _report_fail(event, verbose: bool) -> None:
    if verbose:
        print(f"{event.path}::{event.word} FAILED")
    else:
        sys.stdout.write("F")
        sys.stdout.flush()


def _print_failures(failures) -> None:
    if not failures:
        print()
        return
    print()
    print()
    for event in failures:
        r = event.result
        print(f"FAILED {event.path}::{event.word}")
        if r.expected is not None:
            print(f"  expected: {r.expected}")
            print(f"  actual:   {r.actual}")
        else:
            print("  assertion failed")


def _print_test_summary(passed: int, failures) -> None:
    parts = [f"{passed} passed"]
    if failures:
        parts.append(f"{len(failures)} failed")
    print(", ".join(parts))


if __name__ == "__main__":
    main()
