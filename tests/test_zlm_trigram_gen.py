"""
Unit tests for `examples/zlm-trigram/gen_weights.py`.

The trigram encoder must match z80ai's `TrigramEncoder` byte-for-byte (the polynomial
rolling hash with multiplier 31 mod 65536, then bucket-mod 128). These tests pin
down the algorithm against hand-traced cases so the Forth port can be tested
against the same reference.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


GEN_PATH = Path(__file__).parent.parent / "examples" / "zlm-trigram" / "gen_weights.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("zlm_tier_c_gen", GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestHashTrigram:

    @pytest.mark.parametrize("trigram,expected_h", [
        ("aaa", ((((0 * 31 + ord('a')) & 0xFFFF) * 31 + ord('a')) & 0xFFFF) * 31 + ord('a') & 0xFFFF),
        ("   ", ((((0 * 31 + 32) & 0xFFFF) * 31 + 32) & 0xFFFF) * 31 + 32 & 0xFFFF),
        ("abc", ((((0 * 31 + 97) & 0xFFFF) * 31 + 98) & 0xFFFF) * 31 + 99 & 0xFFFF),
    ])
    def test_hash_matches_polynomial_31_mod_65536(self, gen, trigram, expected_h):
        assert gen.raw_hash(trigram) == expected_h, \
            f"raw_hash({trigram!r}) should be the polynomial rolling hash with multiplier 31 mod 65536; expected {expected_h} got {gen.raw_hash(trigram)}"

    def test_hash_is_zero_for_empty_string(self, gen):
        assert gen.raw_hash("") == 0, \
            "raw_hash('') should be 0 (empty product of polynomial accumulator)"

    @pytest.mark.parametrize("trigram", ["abc", "xyz", "   ", "hel", "xxx"])
    def test_bucket_in_range_0_to_127(self, gen, trigram):
        bucket = gen.hash_trigram(trigram, num_buckets=128)
        assert 0 <= bucket < 128, \
            f"hash_trigram({trigram!r}) should yield a bucket in 0..127; got {bucket}"

    def test_bucket_is_modulo_of_raw_hash(self, gen):
        for trigram in ["abc", "xyz", "   ", "hel", "xxx", "lol", "the"]:
            assert gen.hash_trigram(trigram, num_buckets=128) == gen.raw_hash(trigram) % 128, \
                f"hash_trigram({trigram!r}) should equal raw_hash % 128"


class TestEncodeText:

    def test_lowercases_input(self, gen):
        upper = gen.encode("HELLO")
        lower = gen.encode("hello")
        assert upper == lower, \
            "encode should lowercase its input before hashing; HELLO and hello must produce identical buckets"

    def test_pads_with_one_space_each_side(self, gen):
        unpadded_total = sum(gen.encode("HI"))
        assert unpadded_total == 2, \
            f"encode('HI') with one-space pad on each side should produce exactly len('HI')=2 trigrams summing to 2; got {unpadded_total}"

    def test_word_order_invariant_for_same_trigram_set(self, gen):
        a = gen.encode("ab cd")
        b = gen.encode("cd ab")
        assert a == b, \
            "trigram bag-of-counts is word-order invariant when the trigram multiset is identical"

    def test_returns_128_bucket_vector(self, gen):
        vec = gen.encode("hello")
        assert len(vec) == 128, \
            f"encode should return a 128-bucket vector; got length {len(vec)}"

    @pytest.mark.parametrize("text,expected_total", [
        ("a", 1),
        ("ab", 2),
        ("abc", 3),
        ("hello", 5),
        ("hello world", 11),
        ("", 0),
    ])
    def test_count_total_equals_input_length(self, gen, text, expected_total):
        total = sum(gen.encode(text))
        assert total == expected_total, \
            f"encode({text!r}) should produce len(text)={expected_total} trigram increments; got {total}"

    def test_typo_tolerant_partial_overlap(self, gen):
        clean = gen.encode("hello")
        typo = gen.encode("helo")
        overlap = sum(min(c, t) for c, t in zip(clean, typo))
        assert overlap >= 2, \
            f"a one-char typo should preserve at least 2 of 5 original trigrams in bucket counts; got overlap {overlap}"


class TestKnownGroundTruth:

    def test_hello_produces_expected_buckets(self, gen):
        vec = gen.encode("HELLO")
        nonzero = {i: v for i, v in enumerate(vec) if v > 0}
        assert sum(nonzero.values()) == 5, \
            f"HELLO should produce 5 trigram increments; got {sum(nonzero.values())} in {nonzero}"
        for trigram in [" he", "hel", "ell", "llo", "lo "]:
            bucket = gen.hash_trigram(trigram)
            assert nonzero.get(bucket, 0) >= 1, \
                f"bucket for trigram {trigram!r} (={bucket}) should have count >= 1; nonzero buckets: {nonzero}"


class TestWeightGenerationIntegration:

    def test_generate_uses_256_input_dimension(self, gen):
        _, _, layers = gen.generate()
        in_width = len(layers[0][0])
        assert in_width == 256, \
            f"layer 1 should have 256 inputs (128 query + 128 context); got {in_width}"

    def test_generate_final_layer_matches_charset(self, gen):
        _, _, layers = gen.generate()
        out_width = len(layers[-1])
        assert out_width == len(gen.CHARSET), \
            f"final layer width should match CHARSET length; layer={out_width} charset={len(gen.CHARSET)}"

    def test_generate_is_deterministic(self, gen):
        a = gen.generate(seed=gen.SEED)
        b = gen.generate(seed=gen.SEED)
        assert a[0] == b[0], "query string should be deterministic for fixed seed"
        assert a[1] == b[1], "context buckets should be deterministic for fixed seed"
        assert a[2] == b[2], "weights should be deterministic for fixed seed"


class TestForwardWithTrigramInput:

    def test_forward_returns_charset_index(self, gen):
        query, context, layers = gen.generate()
        char_idx = gen.predict_char_index(query, context, layers)
        assert 0 <= char_idx < len(gen.CHARSET), \
            f"predict_char_index should return a valid charset index 0..{len(gen.CHARSET) - 1}; got {char_idx}"

    def test_predicted_char_in_charset(self, gen):
        query, context, layers = gen.generate()
        ch = gen.predict_char(query, context, layers)
        assert ch in gen.CHARSET, \
            f"predicted character should be a member of CHARSET={gen.CHARSET!r}; got {ch!r}"


class TestRoundTrip:

    def test_generated_source_matches_committed_weights_fs(self, gen):
        query, context, layers = gen.generate()
        expected = gen.to_forth_source(query, context, layers)
        weights_fs = Path(gen.__file__).parent / "weights.fs"
        actual = weights_fs.read_text()
        assert actual.rstrip() == expected.rstrip(), \
            "weights.fs has drifted from gen_weights.py — run `python examples/zlm-trigram/gen_weights.py` to regenerate"
