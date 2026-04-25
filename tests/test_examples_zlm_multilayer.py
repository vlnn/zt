"""
End-to-end test for examples/zlm-multilayer (tier B).

Builds main.fs, runs it in the simulator with the ROM font loaded, asserts the
on-screen prediction matches the argmax computed independently in Python by
gen_weights.forward — proving the layer driver, ReLU placement, and argmax all
match the ground-truth model.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_text,
)


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "zlm-multilayer"
MAIN = EXAMPLE_DIR / "main.fs"
GEN = EXAMPLE_DIR / "gen_weights.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("zlm_tier_b_gen", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def expected(gen):
    inputs, layers = gen.generate()
    history = gen.forward(inputs, layers)
    return {
        "inputs": inputs,
        "layers": layers,
        "history": history,
        "logits": history[-1],
        "argmax": gen.argmax(history[-1]),
    }


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


class TestTierBExample:

    def test_main_file_exists(self):
        assert MAIN.is_file(), \
            "examples/zlm-multilayer/main.fs should exist"

    def test_weights_fs_exists(self):
        assert (EXAMPLE_DIR / "weights.fs").is_file(), \
            "examples/zlm-multilayer/weights.fs should exist (run gen_weights.py to regenerate)"

    def test_predicted_index_appears_on_screen(self, screen_text, expected):
        needle = f"predicted: {expected['argmax']}"
        assert needle in screen_text, \
            f"on-screen prediction should match Python ground truth {expected['argmax']}; screen was:\n{screen_text}"

    def test_each_logit_appears_on_screen(self, screen_text, expected):
        for value in expected["logits"]:
            assert str(value) in screen_text, \
                f"final-layer logit {value} should appear on screen; logits {expected['logits']} screen:\n{screen_text}"

    def test_logits_appear_in_order(self, screen_text, expected):
        cursor = 0
        for i, value in enumerate(expected["logits"]):
            idx = screen_text.find(str(value), cursor)
            assert idx >= 0, \
                f"logit[{i}]={value} should appear after position {cursor} in output order; screen:\n{screen_text}"
            cursor = idx + len(str(value))

    def test_banner_shows_demo_title(self, screen_text):
        assert "zlm-multilayer" in screen_text, \
            f"banner should mention 'zlm-multilayer'; got:\n{screen_text}"

    def test_argmax_is_not_zero_for_seed_42(self, expected):
        assert expected["argmax"] != 0, \
            "seed=42 should yield a non-default argmax (so a broken forward defaulting to 0 actually fails); got 0"
