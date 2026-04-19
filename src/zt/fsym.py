"""
zt symbol-table (`.fsym`) reader/writer. Serialises the compiler's words, origin, body cells and string labels to versioned JSON for downstream tooling (inspect, tests).
"""
import json
from pathlib import Path
from typing import Any

from zt.compiler import Compiler, Word
from zt.ir import cells_to_json


FSYM_VERSION = 2


def write_fsym(compiler: Compiler, path: Path) -> None:
    path.write_text(json.dumps(to_dict(compiler), indent=2, sort_keys=True))


def load_fsym(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def to_dict(compiler: Compiler) -> dict[str, Any]:
    return {
        "fsym_version": FSYM_VERSION,
        "origin": compiler.origin,
        "words": {name: _word_dict(word)
                  for name, word in compiler.words.items()
                  if word.address != 0},
        "string_labels": _string_labels(compiler),
    }


def _string_labels(compiler: Compiler) -> dict[str, int]:
    return {name: addr for name, addr in compiler.asm.labels.items()
            if name.startswith("_str_")}


def _word_dict(word: Word) -> dict[str, Any]:
    d: dict[str, Any] = {"address": word.address, "kind": word.kind}
    if word.body:
        d["cells"] = cells_to_json(word.body)
    if word.source_file is not None:
        d["source_file"] = word.source_file
    if word.source_line is not None:
        d["source_line"] = word.source_line
    return d
