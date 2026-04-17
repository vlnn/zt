from __future__ import annotations

from pathlib import Path

import pytest

from zt.compiler import Compiler


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "sierpinski"
MAIN = EXAMPLE_DIR / "main.fs"


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestSierpinskiExample:

    def test_example_files_exist(self):
        assert MAIN.is_file(), "examples/sierpinski/main.fs should exist"
        assert (EXAMPLE_DIR / "lib" / "math.fs").is_file(), (
            "lib/math.fs should exist for the sierpinski example"
        )
        assert (EXAMPLE_DIR / "lib" / "screen.fs").is_file(), (
            "lib/screen.fs should exist for the sierpinski example"
        )

    def test_compiles_cleanly(self, built_compiler):
        assert "main" in built_compiler.words, (
            "sierpinski example should produce a 'main' word"
        )

    @pytest.mark.parametrize("word", [
        "bit-clear?", "attr-addr", "attr!", "sierp-attr", "draw",
    ])
    def test_expected_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"sierpinski should define '{word}' across its multi-file sources"
        )

    def test_require_dedup_registered_math_once(self, built_compiler):
        math_paths = [p for p in built_compiler.included_files
                      if p.name == "math.fs"]
        assert len(math_paths) == 1, (
            "math.fs should appear in included_files exactly once despite "
            "being required from both main.fs and screen.fs"
        )
