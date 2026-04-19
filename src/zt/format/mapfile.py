"""
Symbol-map writer. Emits either Fuse-style (`$ADDR name`) or ZEsarUX-style (`name = $ADDR`) maps, with format auto-detected from the output extension.
"""
from pathlib import Path

from zt.compile.compiler import Compiler, Word


FUSE = "fuse"
ZESARUX = "zesarux"

_EXT_FORMATS = {
    ".map": FUSE,
    ".sym": ZESARUX,
    ".zesarux": ZESARUX,
}


def write_map(compiler: Compiler, path: Path, fmt: str | None = None) -> None:
    resolved = fmt or detect_format(path)
    path.write_text(render(compiler, resolved))


def detect_format(path: Path) -> str:
    return _EXT_FORMATS.get(path.suffix.lower(), FUSE)


def render(compiler: Compiler, fmt: str) -> str:
    lines = [_FORMATTERS[fmt](w) for w in _addressed_words(compiler)]
    return "\n".join(lines) + "\n"


def _addressed_words(compiler: Compiler) -> list[Word]:
    words = [w for w in compiler.words.values() if w.address != 0]
    words.sort(key=lambda w: (w.address, w.name))
    return words


def _fuse_line(word: Word) -> str:
    return f"${word.address:04X} {word.name}"


def _zesarux_line(word: Word) -> str:
    return f"{word.name} = ${word.address:04X}"


_FORMATTERS = {
    FUSE: _fuse_line,
    ZESARUX: _zesarux_line,
}
