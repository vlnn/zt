"""
Unit tests for `examples/zlm-multilayer/gen_weights.py`.

The generator is the ground truth for tier (B): it produces the synthetic
weights/inputs baked into `weights.fs` and computes the expected argmax that
the on-Spectrum forward pass must reproduce.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


GEN_PATH = Path(__file__).parent.parent / "examples" / "zlm-multilayer" / "gen_weights.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("zlm_tier_b_gen", GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPackByte:

    @pytest.mark.parametrize("weights,expected", [
        ([0, 0, 0, 0], 0x00),
        ([3, 3, 3, 3], 0xFF),
        ([1, 0, 0, 0], 0x01),
        ([0, 1, 0, 0], 0x04),
        ([0, 0, 1, 0], 0x10),
        ([0, 0, 0, 1], 0x40),
        ([3, 1, 0, 2], 0b10_00_01_11),
        ([2, 2, 2, 2], 0xAA),
    ])
    def test_packs_lsb_first_four_per_byte(self, gen, weights, expected):
        assert gen.pack_byte(weights) == expected, \
            f"pack_byte({weights}) should put the first weight in the low 2 bits LSB-first; expected {expected:#04x} got {gen.pack_byte(weights):#04x}"


class TestPackLayer:

    def test_concatenates_packed_rows_in_output_order(self, gen):
        weights = [
            [0, 0, 0, 0, 3, 3, 3, 3],
            [1, 1, 1, 1, 2, 2, 2, 2],
        ]
        packed = gen.pack_layer(weights)
        assert packed == bytes([0x00, 0xFF, 0x55, 0xAA]), \
            f"pack_layer should pack each row LSB-first then concatenate rows in order; got {packed.hex()}"

    @pytest.mark.parametrize("bad_row_width", [1, 2, 3, 5, 6, 7])
    def test_rejects_row_width_not_multiple_of_four(self, gen, bad_row_width):
        weights = [[0] * bad_row_width]
        with pytest.raises(AssertionError, match="multiple of 4"):
            gen.pack_layer(weights)


class TestForwardSemantics:

    def test_weight_bias_subtracts_two_from_packed_value(self, gen):
        inputs = [10]
        layers = [[[0]]]
        assert gen.forward(inputs, layers)[-1] == [-20], \
            "raw weight 0 should map to -2 after the bias-2 subtraction; expected -20 for input 10"

    @pytest.mark.parametrize("raw,expected_weight", [
        (0, -2), (1, -1), (2, 0), (3, +1),
    ])
    def test_each_raw_value_maps_to_signed_weight(self, gen, raw, expected_weight):
        inputs = [10, 10, 10, 10]
        layers = [[[raw, raw, raw, raw]]]
        out = gen.forward(inputs, layers)[-1][0]
        assert out == expected_weight * 40, \
            f"raw weight {raw} should map to signed {expected_weight}; expected {expected_weight*40} got {out}"

    def test_relu_clamps_negative_in_intermediate_layer(self, gen):
        inputs = [10, 10]
        layers = [[[0, 0]], [[3]]]
        out = gen.forward(inputs, layers)[-1]
        assert out == [0], \
            f"intermediate ReLU should clamp -40 to 0 before the next layer; expected [0] got {out}"

    def test_no_relu_on_final_layer(self, gen):
        inputs = [10, 10]
        layers = [[[0, 0]]]
        out = gen.forward(inputs, layers)[-1]
        assert out == [-40], \
            f"final layer must not apply ReLU; expected [-40] got {out}"

    def test_returns_all_intermediate_activations(self, gen):
        inputs = [10, 10]
        layers = [[[3, 3]], [[3]]]
        all_acts = gen.forward(inputs, layers)
        assert len(all_acts) == 3, \
            f"forward should return inputs + each layer's outputs (3 entries for 2-layer net); got {len(all_acts)}"
        assert all_acts[0] == inputs, \
            "first entry should be the raw inputs"
        assert all_acts[-1] == [20], \
            f"final entry should be the final logits; expected [20] got {all_acts[-1]}"


class TestArgmax:

    @pytest.mark.parametrize("values,expected", [
        ([0], 0),
        ([1, 2, 3], 2),
        ([3, 2, 1], 0),
        ([-1, -2, -3], 0),
        ([5, 5, 5], 0),
        ([0, 7, 3, 7, 1], 1),
    ])
    def test_returns_index_of_first_maximum(self, gen, values, expected):
        assert gen.argmax(values) == expected, \
            f"argmax({values}) should return index of first max; expected {expected} got {gen.argmax(values)}"


class TestGenerateDeterminism:

    def test_same_seed_yields_same_inputs_and_layers(self, gen):
        inputs_a, layers_a = gen.generate(seed=123)
        inputs_b, layers_b = gen.generate(seed=123)
        assert inputs_a == inputs_b, \
            "generate(seed=123) must be deterministic in inputs"
        assert layers_a == layers_b, \
            "generate(seed=123) must be deterministic in layer weights"

    def test_different_seeds_yield_different_inputs(self, gen):
        inputs_a, _ = gen.generate(seed=1)
        inputs_b, _ = gen.generate(seed=2)
        assert inputs_a != inputs_b, \
            "different seeds should normally diverge on the input vector"


class TestArchitectureShape:

    def test_inputs_match_first_layer_width(self, gen):
        inputs, layers = gen.generate()
        assert len(inputs) == gen.ARCHITECTURE[0], \
            f"input vector should have ARCHITECTURE[0] entries; got {len(inputs)}"

    def test_layers_match_consecutive_pairs(self, gen):
        _, layers = gen.generate()
        widths = gen.ARCHITECTURE
        assert len(layers) == len(widths) - 1, \
            f"there should be N-1 layers for N widths; got {len(layers)} for widths {widths}"
        for i, (prev, cur) in enumerate(zip(widths, widths[1:])):
            assert len(layers[i]) == cur, \
                f"layer {i} should have {cur} output rows; got {len(layers[i])}"
            for row in layers[i]:
                assert len(row) == prev, \
                    f"each row of layer {i} should have {prev} weights; got {len(row)}"

    def test_every_layer_input_width_is_multiple_of_four(self, gen):
        widths = gen.ARCHITECTURE
        for prev in widths[:-1]:
            assert prev % 4 == 0, \
                f"every layer's input width must be a multiple of 4 (kernel constraint); got width {prev} in {widths}"


class TestForthSourceShape:

    @pytest.fixture(scope="class")
    def source(self, gen):
        inputs, layers = gen.generate()
        return gen.to_forth_source(inputs, layers)

    def test_emits_create_block_for_inputs(self, source):
        assert "create acts0" in source, \
            "Forth source should declare an `acts0` create block for the input activations"

    def test_emits_create_block_per_layer(self, source, gen):
        for i in range(1, len(gen.ARCHITECTURE)):
            assert f"create weights{i}" in source, \
                f"Forth source should declare `weights{i}` create block for layer {i}"

    def test_input_cells_use_comma_for_two_byte_cells(self, source, gen):
        inputs, _ = gen.generate()
        for value in inputs:
            assert f"{value} ," in source, \
                f"input value {value} should appear as a 16-bit `, ` literal in the source"

    def test_weights_use_c_comma_for_packed_bytes(self, source):
        assert " c," in source, \
            "weights should appear as `c,` byte literals (one packed byte per c,)"


class TestRoundTrip:

    def test_generated_source_matches_committed_weights_fs(self, gen):
        inputs, layers = gen.generate()
        expected = gen.to_forth_source(inputs, layers)
        weights_fs = Path(gen.__file__).parent / "weights.fs"
        actual = weights_fs.read_text()
        assert actual.rstrip() == expected.rstrip(), \
            "weights.fs has drifted from gen_weights.py — run `python examples/zlm-multilayer/gen_weights.py` to regenerate"
