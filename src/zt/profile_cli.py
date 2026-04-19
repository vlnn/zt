"""
`zt profile` subcommand. Supports single-run and image-input modes, saving / diffing against a baseline `.zprof`, JSON output, and regression gating via `--fail-if-slower`.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from zt.compiler import CompileError
from zt.image_loader import default_map_path, load_sna, read_map
from zt.profile import ProfileReport, Profiler, build_word_ranges, format_report
from zt.profile_io import (
    DiffEntry,
    diff_reports,
    read_zprof,
    regressions,
    write_zprof,
)


EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_USAGE = 2
EXIT_RUNTIME = 3


@dataclass(frozen=True)
class ProfileArgs:
    source: Path | None
    image: Path | None
    symbols: Path | None
    max_ticks: int
    words: list[str]
    baseline: Path | None
    save: Path | None
    json_output: bool
    fail_if_slower: float | None


def register_profile(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("profile", help="profile a compiled Forth program")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--source", type=Path, default=None,
                     help=".fs source to compile and profile")
    src.add_argument("--image", type=Path, default=None,
                     help="pre-built .sna image to profile")
    p.add_argument("--symbols", type=Path, default=None,
                   help="symbol map for --image (default: sibling .map)")
    p.add_argument("--max-ticks", type=int, default=1_000_000,
                   dest="max_ticks", metavar="N",
                   help="instruction budget for the run (default: 1_000_000)")
    p.add_argument("--words", type=_parse_word_list, default=[],
                   help="comma-separated word names to focus on")
    p.add_argument("--baseline", type=Path, default=None,
                   help="compare against a previously-saved .zprof snapshot")
    p.add_argument("--save", type=Path, default=None,
                   help="write .prof (text) and .zprof (JSON) snapshots to this path")
    p.add_argument("--json", dest="json_output", action="store_true", default=False,
                   help="emit JSON report to stdout instead of a text table")
    p.add_argument("--fail-if-slower", type=float, default=None,
                   dest="fail_if_slower", metavar="PCT",
                   help="exit nonzero if any selected word regressed by more than PCT%%")


def _parse_word_list(s: str) -> list[str]:
    return [w.strip() for w in s.split(",") if w.strip()]


def run_profile_command(args: ProfileArgs, out: TextIO, err: TextIO) -> int:
    try:
        report = _produce_report(args)
    except _UserError as e:
        print(f"error: {e}", file=err)
        return e.exit_code

    selected = _select_words(args, report, err)
    if selected is None:
        return EXIT_RUNTIME

    if args.save is not None:
        _save_snapshots(args.save, report)

    if args.baseline is not None:
        return _render_diff_mode(args, report, selected, out, err)

    return _render_single_mode(args, report, selected, out)


def _produce_report(args: ProfileArgs) -> ProfileReport:
    if args.source is not None:
        return _profile_source(args.source, args.max_ticks)
    return _profile_image(args.image, args.symbols, args.max_ticks)


def _profile_source(source: Path, max_ticks: int) -> ProfileReport:
    if not source.exists():
        raise _UserError(f"{source} not found", EXIT_RUNTIME)
    try:
        compiler = _compile_fs(source)
    except CompileError as e:
        raise _UserError(f"compile failed: {e}", EXIT_RUNTIME) from e
    image = compiler.build()
    labels = {name: w.address for name, w in compiler.words.items()}
    return _run_profiled(
        image_bytes=image,
        origin=compiler.origin,
        entry=compiler.words["_start"].address,
        labels=labels,
        max_ticks=max_ticks,
    )


def _profile_image(image_path: Path, symbols: Path | None, max_ticks: int) -> ProfileReport:
    if not image_path.exists():
        raise _UserError(f"{image_path} not found", EXIT_RUNTIME)
    map_path = symbols or default_map_path(image_path)
    if not map_path.exists():
        raise _UserError(f"symbol map {map_path} not found", EXIT_RUNTIME)
    labels = read_map(map_path)
    if "_start" not in labels:
        raise _UserError(f"{map_path} has no _start symbol", EXIT_RUNTIME)
    mem = load_sna(image_path)
    return _run_profiled_raw(
        mem=mem,
        entry=labels["_start"],
        labels=labels,
        max_ticks=max_ticks,
    )


def _compile_fs(source: Path):
    from zt.compiler import Compiler
    c = Compiler()
    c.include_stdlib()
    c.compile_source(source.read_text(), source=str(source))
    c.compile_main_call()
    return c


def _run_profiled(
    image_bytes: bytes,
    origin: int,
    entry: int,
    labels: dict[str, int],
    max_ticks: int,
) -> ProfileReport:
    from zt.sim import SPECTRUM_FONT_BASE, TEST_FONT, Z80
    m = Z80()
    m.load(origin, image_bytes)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = entry
    code_end = origin + len(image_bytes)
    profiler = Profiler(build_word_ranges(labels, code_end=code_end))
    m.run(max_ticks=max_ticks, profiler=profiler)
    return profiler.report()


def _run_profiled_raw(
    mem: bytearray,
    entry: int,
    labels: dict[str, int],
    max_ticks: int,
) -> ProfileReport:
    from zt.sim import Z80
    m = Z80()
    m.mem = mem
    m.pc = entry
    profiler = Profiler(build_word_ranges(labels))
    m.run(max_ticks=max_ticks, profiler=profiler)
    return profiler.report()


def _select_words(
    args: ProfileArgs,
    report: ProfileReport,
    err: TextIO,
) -> set[str] | None:
    if not args.words:
        return set()
    present = {e.word for e in report.entries}
    missing = [w for w in args.words if w not in present]
    if missing:
        print(
            f"error: words not found in profile: {', '.join(missing)}",
            file=err,
        )
        return None
    return set(args.words)


def _save_snapshots(base_path: Path, report: ProfileReport) -> None:
    prof_path = base_path.with_suffix(".prof")
    zprof_path = base_path.with_suffix(".zprof")
    prof_path.write_text(format_report(report) + "\n")
    write_zprof(zprof_path, report)


def _render_single_mode(
    args: ProfileArgs,
    report: ProfileReport,
    selected: set[str],
    out: TextIO,
) -> int:
    if args.json_output:
        print(_report_to_json(_filter_report(report, selected)), file=out)
    else:
        print(_format_single_table(report, selected), file=out)
    return EXIT_OK


def _render_diff_mode(
    args: ProfileArgs,
    report: ProfileReport,
    selected: set[str],
    out: TextIO,
    err: TextIO,
) -> int:
    if not args.baseline.exists():
        print(f"error: baseline {args.baseline} not found", file=err)
        return EXIT_RUNTIME
    baseline = read_zprof(args.baseline)
    diffs = diff_reports(baseline, report)
    filtered = _filter_diffs(diffs, selected)
    if args.json_output:
        print(_diffs_to_json(filtered), file=out)
    else:
        print(_format_diff_table(filtered), file=out)

    if args.fail_if_slower is not None:
        regs = regressions(diffs, args.fail_if_slower, selected or None)
        if regs:
            print(
                f"regressions over {args.fail_if_slower}%: "
                + ", ".join(r.word for r in regs),
                file=err,
            )
            return EXIT_REGRESSION
    return EXIT_OK


def _filter_report(report: ProfileReport, selected: set[str]) -> ProfileReport:
    if not selected:
        return report
    entries = tuple(e for e in report.entries if e.word in selected)
    return ProfileReport(
        entries=entries,
        total_ticks=report.total_ticks,
        total_t_states=report.total_t_states,
    )


def _filter_diffs(diffs: list[DiffEntry], selected: set[str]) -> list[DiffEntry]:
    if not selected:
        return diffs
    return [d for d in diffs if d.word in selected]


def _format_single_table(report: ProfileReport, selected: set[str]) -> str:
    header = f"{'Word':<20} {'Calls':>6} {'Self':>8} {'Self%':>7} {'Incl':>10} {'Incl%':>7} {'Avg':>8}"
    lines = [header, "-" * len(header)]
    total = report.total_t_states or 1
    filtered = [e for e in report.entries if not selected or e.word in selected]
    filtered.sort(key=lambda e: -e.incl_t_states)
    for e in filtered:
        self_pct = 100.0 * e.t_states / total
        incl_pct = 100.0 * e.incl_t_states / total
        avg = e.incl_t_states // e.calls if e.calls else 0
        lines.append(
            f"{e.word:<20} {e.calls:>6} {e.t_states:>8} {self_pct:>6.1f}"
            f" {e.incl_t_states:>10} {incl_pct:>6.1f} {avg:>8}"
        )
    lines.append("")
    lines.append(
        f"Total: {report.total_t_states} T-states across {report.total_ticks} instructions"
    )
    return "\n".join(lines)


def _format_diff_table(diffs: list[DiffEntry]) -> str:
    header = f"{'Word':<20} {'Base Incl':>12} {'Curr Incl':>12} {'Δ':>10} {'Δ%':>8}"
    lines = [header, "-" * len(header)]
    for d in diffs:
        lines.append(_format_diff_row(d))
    return "\n".join(lines)


def _format_diff_row(d: DiffEntry) -> str:
    base = "—" if d.base_incl is None else str(d.base_incl)
    curr = "—" if d.curr_incl is None else str(d.curr_incl)
    delta = "—" if d.delta is None else f"{d.delta:+d}"
    pct = "—" if d.pct is None else f"{d.pct:+.1f}%"
    return f"{d.word:<20} {base:>12} {curr:>12} {delta:>10} {pct:>8}"


def _report_to_json(report: ProfileReport) -> str:
    return json.dumps({
        "total_ticks": report.total_ticks,
        "total_t_states": report.total_t_states,
        "entries": [
            {
                "word": e.word,
                "calls": e.calls,
                "ticks": e.ticks,
                "self_t_states": e.t_states,
                "incl_t_states": e.incl_t_states,
            }
            for e in report.entries
        ],
    }, indent=2)


def _diffs_to_json(diffs: list[DiffEntry]) -> str:
    return json.dumps([
        {
            "word": d.word,
            "base_incl": d.base_incl,
            "curr_incl": d.curr_incl,
            "delta": d.delta,
            "pct": d.pct,
        }
        for d in diffs
    ], indent=2)


class _UserError(Exception):

    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def args_from_namespace(ns: argparse.Namespace) -> ProfileArgs:
    return ProfileArgs(
        source=ns.source,
        image=ns.image,
        symbols=ns.symbols,
        max_ticks=ns.max_ticks,
        words=ns.words,
        baseline=ns.baseline,
        save=ns.save,
        json_output=ns.json_output,
        fail_if_slower=ns.fail_if_slower,
    )
