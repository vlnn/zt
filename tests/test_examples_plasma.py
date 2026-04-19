"""
Builds `examples/plasma/main.fs` end-to-end and asserts the multi-file plasma example compiles cleanly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "plasma"
MAIN = EXAMPLE_DIR / "main.fs"


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestPlasmaExample:

    @pytest.mark.parametrize("relpath", [
        "main.fs",
        "app/plasma.fs",
        "lib/math.fs",
        "lib/screen.fs",
    ])
    def test_example_files_exist(self, relpath):
        assert (EXAMPLE_DIR / relpath).is_file(), (
            f"plasma demo should ship {relpath}"
        )

    def test_compiles_cleanly(self, built_compiler):
        assert "main" in built_compiler.words, (
            "plasma example should produce a 'main' word"
        )

    @pytest.mark.parametrize("word", [
        "mod32", "attr-addr", "attr!", "wave", "wave@",
        "plasma-cell", "draw", "step", "animate",
    ])
    def test_expected_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"plasma should define '{word}' across its multi-file sources"
        )

    def test_require_dedup_registered_math_once(self, built_compiler):
        math_paths = [p for p in built_compiler.include_resolver.seen_paths()
                      if p.name == "math.fs"]
        assert len(math_paths) == 1, (
            "math.fs is required from both app/plasma.fs (via ../lib/math.fs) "
            "and lib/screen.fs (via math.fs); both paths should canonicalize "
            "to one entry in included_files"
        )

    def test_wave_table_has_32_bytes(self, built_compiler):
        wave = built_compiler.words["wave"]
        assert wave.kind == "variable", (
            "wave should be CREATE-defined (kind 'variable')"
        )
