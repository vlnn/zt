#!/usr/bin/env python3
"""Regenerate examples/zlm-tinychat-48k/model.fs from the 128K source.

Differences vs the 128K version:
  - Biases written as 8-bit signed bytes (c,) — values fit in -128..127
  - No `in-bank` / `end-bank` directives — weights live in flat memory
  - No `bank-fcN` constants — the main code drops the bank! calls
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "examples" / "zlm-tinychat" / "model.fs"
DST = ROOT / "examples" / "zlm-tinychat-48k" / "model.fs"


def parse_cells(text: str) -> list[int]:
    return [int(tok) for tok in re.findall(r"-?\d+", text)]


def signed_byte_lit(value: int) -> str:
    as_signed = value if value < 0x8000 else value - 0x10000
    if not -128 <= as_signed <= 127:
        raise ValueError(f"bias {value} (={as_signed}) does not fit in int8")
    return f"${as_signed & 0xFF:02X}"


def format_bias_line(values: list[int]) -> str:
    return "  " + " ".join(f"{signed_byte_lit(v)} c," for v in values)


def chunks(seq: list, n: int) -> list[list]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


SECTION_BIAS_RE = re.compile(
    r"^create (bias\d+)\n((?:  [^\n]*\n)+)",
    re.MULTILINE,
)


def rewrite_biases(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        body = match.group(2)
        cells = parse_cells(body)
        rows = [format_bias_line(row) for row in chunks(cells, 8)]
        return f"create {name}\n" + "\n".join(rows) + "\n"

    return SECTION_BIAS_RE.sub(replace, text)


def strip_bank_directives(text: str) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith("in-bank") or stripped == "end-bank":
            continue
        if re.match(r"^\d+ constant bank-fc\d+$", stripped):
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def transform(text: str) -> str:
    return strip_bank_directives(rewrite_biases(text))


def main() -> int:
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(transform(SRC.read_text()))
    print(f"wrote {DST.relative_to(ROOT)} ({DST.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
