"""
Builds `examples/zlm-layer/main.fs` and runs it in the simulator, asserting that
the four expected output values (377, 1135, 190, 1175) appear on screen.

The expected values were computed independently in Python from the same
weights and activations baked into the .fs file (random.seed(42)).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_text,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "zlm-layer"
MAIN = EXAMPLE_DIR / "main.fs"

EXPECTED_OUTPUTS = (377, 1135, 190, 1175)


@pytest.fixture(scope="module")
def screen_text() -> str:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    image = c.build()

    m = Z80()
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = c.words["_start"].address
    m.run(max_ticks=2_000_000)

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0)
    return raw.decode("ascii", errors="replace")


class TestZlmLayerExample:

    def test_main_file_exists(self):
        assert MAIN.is_file(), \
            "examples/zlm-layer/main.fs should exist"

    @pytest.mark.parametrize("expected", EXPECTED_OUTPUTS)
    def test_each_output_value_appears_on_screen(self, screen_text, expected):
        assert str(expected) in screen_text, \
            f"expected output {expected} should appear in screen text after forward pass; got:\n{screen_text}"

    def test_output_values_appear_in_order(self, screen_text):
        positions = [screen_text.find(str(v)) for v in EXPECTED_OUTPUTS]
        for i, pos in enumerate(positions):
            assert pos >= 0, \
                f"output[{i}]={EXPECTED_OUTPUTS[i]} should appear on screen, screen was:\n{screen_text}"
        assert positions == sorted(positions), \
            f"output values should appear top-to-bottom in order 0..3; positions={positions}"

    def test_banner_shows_demo_title(self, screen_text):
        assert "zlm-layer" in screen_text, \
            f"screen banner should mention 'zlm-layer'; got:\n{screen_text}"
