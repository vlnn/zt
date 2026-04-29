"""Survey all examples by shelling out to `zt build` with and without
--tree-shake; report image-size deltas. Mirrors the actual production
build flags from each example.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Example:
    name: str
    source: str
    flags: tuple[str, ...] = ()


EXAMPLES = (
    Example("hello",            "examples/hello.fs"),
    Example("counter",          "examples/counter.fs"),
    Example("sierpinski",       "examples/sierpinski.fs"),
    Example("sierpinski-2",     "examples/sierpinski-2.fs"),
    Example("sierpinski-3",     "examples/sierpinski-3.fs"),
    Example("sierpinski-dir",   "examples/sierpinski/main.fs"),
    Example("plasma",           "examples/plasma/main.fs"),
    Example("plasma2",          "examples/plasma2/main.fs"),
    Example("plasma3",          "examples/plasma3/main.fs"),
    Example("plasma4",          "examples/plasma4/main.fs"),
    Example("plasma-128k",      "examples/plasma-128k/main.fs",
            ("--target", "128k")),
    Example("reaction",         "examples/reaction/main.fs"),
    Example("mined-out",        "examples/mined-out/main.fs"),
    Example("sprite-demo",      "examples/sprite-demo/main.fs"),
    Example("shadow-flip",      "examples/shadow-flip/main.fs",
            ("--target", "128k")),
    Example("bank-rotator",     "examples/bank-rotator/main.fs",
            ("--target", "128k")),
    Example("bank-table",       "examples/bank-table/main.fs",
            ("--target", "128k")),
    Example("zlm-emit-test",    "examples/zlm-emit-test/main.fs",
            ("--target", "128k")),
    Example("zlm-layer",        "examples/zlm-layer/main.fs",
            ("--target", "128k")),
    Example("zlm-multilayer",   "examples/zlm-multilayer/main.fs",
            ("--target", "128k")),
    Example("zlm-smoke",        "examples/zlm-smoke/main.fs",
            ("--target", "128k")),
    Example("zlm-trigram",      "examples/zlm-trigram/main.fs",
            ("--target", "128k")),
    Example("zlm-tinychat",     "examples/zlm-tinychat/main.fs",
            ("--target", "128k")),
    Example("zlm-tinychat-48k", "examples/zlm-tinychat-48k/main.fs",
            ("--target", "48k", "--origin", "0x5CB6",
             "--rstack", "0xFFA0", "--dstack", "0xFFC0",
             "--no-inline-next", "--no-stdlib")),
)


CODE_BYTES_RE = re.compile(r"\((\d+) bytes code")


def _build(example: Example, *, mode: str, out: Path):
    """mode is 'eager' (--no-tree-shake), 'auto' (default), or 'strict' (--tree-shake)."""
    cmd = ["uv", "run", "python", "-m", "zt.cli", "build",
           str(ROOT / example.source), "-o", str(out), *example.flags]
    if mode == "strict":
        cmd.append("--tree-shake")
    elif mode == "eager":
        cmd.append("--no-tree-shake")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip().splitlines()
        msg = err[-1] if err else "no output"
        if "--tree-shake does not yet support" in msg:
            return "unsupported"
        return f"ERR: {msg[:50]}"
    match = CODE_BYTES_RE.search(proc.stdout)
    if not match:
        return "ERR: no size"
    return int(match.group(1))


def main() -> None:
    print(f"{'example':<22} {'eager':>9} {'tree-shaken':>13} {'saved':>9} {'%':>6}")
    print("-" * 66)
    out_eager = ROOT / "build" / "_survey_eager.bin"
    out_auto = ROOT / "build" / "_survey_auto.bin"
    out_eager.parent.mkdir(exist_ok=True)
    total_eager = total_auto = 0
    fallback_count = 0
    for ex in EXAMPLES:
        eager = _build(ex, mode="eager", out=out_eager)
        if isinstance(eager, str):
            print(f"{ex.name:<22} {eager}")
            continue
        auto = _build(ex, mode="auto", out=out_auto)
        if isinstance(auto, str):
            print(f"{ex.name:<22} {eager:>9} {auto:>13}")
            continue
        if auto == eager:
            note = "  (auto-tree-shake fell back to eager — uses ' / ['] / in-bank)"
            fallback_count += 1
        else:
            note = ""
        saved = eager - auto
        pct = 100.0 * saved / eager if eager else 0
        print(f"{ex.name:<22} {eager:>9} {auto:>13} {saved:>9} {pct:>5.1f}%{note}")
        total_eager += eager
        total_auto += auto
    print("-" * 66)
    if total_eager:
        saved = total_eager - total_auto
        pct = 100.0 * saved / total_eager
        print(f"{'TOTAL':<22} {total_eager:>9} {total_auto:>13} "
              f"{saved:>9} {pct:>5.1f}%")
        print()
        print(f"Auto-tree-shake fell back to eager for {fallback_count} examples "
              f"(features unsupported by tree-shaker).")


if __name__ == "__main__":
    main()
