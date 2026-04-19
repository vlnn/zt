"""
Sjasmplus-style SLD (source-level debug) writer. Emits the version/device header plus `|T` trace lines from the compiler source map and `|L` label lines for each word.
"""
from pathlib import Path

from zt.compiler import Compiler, Word


HEADER = ("|SLD.data.version|1\n"
          "||||||||device:ZXSPECTRUM48\n")


def write_sld(compiler: Compiler, path: Path) -> None:
    path.write_text(render(compiler))


def render(compiler: Compiler) -> str:
    body = "\n".join(_all_lines(compiler))
    if not body:
        return HEADER
    return HEADER + body + "\n"


def _all_lines(compiler: Compiler) -> list[str]:
    return [*_trace_lines(compiler), *_label_lines(compiler)]


def _trace_lines(compiler: Compiler) -> list[str]:
    return [_pipe_line(e.source_file, e.line, e.col, e.address, "T", "")
            for e in compiler.source_map]


def _label_lines(compiler: Compiler) -> list[str]:
    labelled = [w for w in compiler.words.values() if _has_location(w)]
    labelled.sort(key=lambda w: w.address)
    return [_pipe_line(w.source_file, w.source_line, 1, w.address, "L", w.name)
            for w in labelled]


def _has_location(word: Word) -> bool:
    return word.source_file is not None and word.source_line is not None


def _pipe_line(source: str, line: int, col: int, address: int,
               kind: str, data: str) -> str:
    return f"{source}|{line}|{col}|{source}|{line}|0|{address}|{kind}|{data}"
