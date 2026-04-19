"""
Tests for the lower-level inline helpers: `primitive_name`, `extract_inline_body`, and `build_inline_registry`.
"""
from __future__ import annotations

import pytest

from zt.asm import Asm
from zt.inline_bodies import (
    build_inline_registry,
    extract_inline_body,
    primitive_name,
)
from zt.primitives import (
    PRIMITIVES,
    create_2drop,
    create_2dup,
    create_drop,
    create_dup,
    create_halt,
    create_next,
    create_nip,
    create_one_minus,
    create_one_plus,
    create_over,
    create_plus,
    create_rot,
    create_swap,
    create_two_slash,
    create_two_star,
)


_JP_TO_NEXT_AT_ZERO = bytes([0xC3, 0x00, 0x00])


class TestPrimitiveName:

    @pytest.mark.parametrize("creator,expected", [
        (create_dup,        "dup"),
        (create_drop,       "drop"),
        (create_plus,       "plus"),
        (create_one_plus,   "one_plus"),
        (create_two_star,   "two_star"),
    ], ids=lambda v: v.__name__ if callable(v) else str(v))
    def test_strips_create_prefix(self, creator, expected):
        assert primitive_name(creator) == expected, \
            f"{creator.__name__} should yield registry key {expected!r}"

    def test_function_without_prefix_returns_raw_name(self):
        def someotherfn(a): pass
        assert primitive_name(someotherfn) == "someotherfn", \
            "functions without 'create_' prefix should return their name unchanged"


class TestExtractInlineBody:

    @pytest.mark.parametrize("creator,expected_prefix", [
        (create_drop,       bytes([0xE1])),
        (create_swap,       bytes([0xE3])),
        (create_nip,        bytes([0xD1])),
        (create_dup,        bytes([0xE5])),
        (create_one_plus,   bytes([0x23])),
        (create_one_minus,  bytes([0x2B])),
        (create_two_star,   bytes([0x29])),
        (create_plus,       bytes([0xD1, 0x19])),
        (create_2drop,      bytes([0xE1, 0xE1])),
    ], ids=lambda v: v.__name__ if callable(v) else v.hex())
    def test_body_starts_with_primitive_opcodes(self, creator, expected_prefix):
        body = extract_inline_body(creator)
        assert body is not None, \
            f"{creator.__name__} should have an extractable inline body"
        assert body.startswith(expected_prefix), \
            f"{creator.__name__} body should start with {expected_prefix.hex()}, got {body[:len(expected_prefix)].hex()}"

    @pytest.mark.parametrize("creator", [
        create_dup, create_drop, create_swap, create_over, create_rot,
        create_nip, create_plus, create_one_plus, create_one_minus,
        create_two_star, create_two_slash, create_2dup, create_2drop,
    ], ids=lambda c: c.__name__)
    def test_extracted_body_no_longer_contains_trailing_dispatch(self, creator):
        body = extract_inline_body(creator)
        assert body is not None, \
            f"{creator.__name__} should have an extractable inline body"
        if len(body) >= 3:
            assert body[-3:] != _JP_TO_NEXT_AT_ZERO, \
                f"{creator.__name__} still has a trailing JP NEXT after extraction"

    def test_halt_is_not_extractable(self):
        assert extract_inline_body(create_halt) is None, \
            "halt does not end with a dispatch and must be reported as non-extractable"

    def test_create_next_is_not_extractable(self):
        assert extract_inline_body(create_next) is None, \
            "create_next is the dispatcher itself and must be rejected explicitly"

    def test_primitive_with_unresolved_external_label_is_not_extractable(self):
        def create_bogus(a):
            a.label("BOGUS")
            a.push_hl()
            a.call("_never_defined_anywhere")
            a.dispatch()
        assert extract_inline_body(create_bogus) is None, \
            "a primitive referencing an external undefined label must be reported as non-extractable, not crash"

    def test_extracted_body_is_three_bytes_shorter_than_full_primitive(self):
        a = Asm(0x0000, inline_next=False)
        a.label("NEXT")
        create_plus(a)
        full = a.resolve()
        body = extract_inline_body(create_plus)
        assert body is not None, "plus should be extractable"
        assert len(body) == len(full) - 3, \
            "extract should strip exactly the 3-byte JP NEXT tail"

    def test_extracted_body_is_a_prefix_of_the_full_primitive(self):
        a = Asm(0x0000, inline_next=False)
        a.label("NEXT")
        create_swap(a)
        full = a.resolve()
        body = extract_inline_body(create_swap)
        assert body is not None, "swap should be extractable"
        assert full.startswith(body), \
            "extracted body should be a prefix of the unmodified primitive bytes"

    def test_extracted_body_returns_immutable_bytes(self):
        body = extract_inline_body(create_dup)
        assert isinstance(body, bytes), \
            "extract_inline_body should return bytes, not bytearray, to prevent accidental mutation"


class TestBuildInlineRegistry:

    def test_dup_is_in_registry_under_short_name(self):
        registry = build_inline_registry([create_dup, create_plus])
        assert "dup" in registry, "dup should be keyed under its stripped-prefix name"

    def test_halt_is_filtered_out(self):
        registry = build_inline_registry([create_dup, create_halt, create_plus])
        assert "halt" not in registry, \
            "primitives without a dispatch tail must be filtered from the registry"
        assert "dup" in registry and "plus" in registry, \
            "other primitives should still be present alongside a filtered halt"

    def test_create_next_is_filtered_out(self):
        registry = build_inline_registry([create_next, create_dup])
        assert "next" not in registry, \
            "the dispatcher itself must never appear in the inline registry"
        assert "dup" in registry, \
            "other primitives should still be present alongside a filtered create_next"

    def test_primitive_with_external_label_is_filtered_out(self):
        def create_references_external(a):
            a.label("REFEXT")
            a.push_hl()
            a.call("_not_defined_in_this_asm")
            a.dispatch()
        registry = build_inline_registry([create_dup, create_references_external])
        assert "references_external" not in registry, \
            "primitives that can't resolve standalone must be filtered, not crash the whole build"
        assert "dup" in registry, \
            "a crash during one primitive must not prevent extraction of the others"

    def test_full_primitives_list_does_not_crash(self):
        registry = build_inline_registry(PRIMITIVES)
        assert "dup" in registry, \
            "building the registry from the full PRIMITIVES list must succeed and include dup"

    def test_registry_values_are_bytes(self):
        registry = build_inline_registry([create_plus])
        assert isinstance(registry["plus"], bytes), \
            "registry entries should be immutable bytes"

    @pytest.mark.parametrize("name", [
        "dup", "drop", "swap", "over", "nip", "rot",
        "plus", "one_plus", "one_minus", "two_star",
        "2dup", "2drop",
    ])
    def test_full_primitives_list_contains_expected_entries(self, name):
        registry = build_inline_registry(PRIMITIVES)
        assert name in registry, \
            f"{name} should appear when registry is built from the full PRIMITIVES list"

    def test_full_primitives_list_excludes_halt(self):
        registry = build_inline_registry(PRIMITIVES)
        assert "halt" not in registry, \
            "halt must not leak into the registry built from the full PRIMITIVES list"

    def test_full_primitives_list_excludes_next(self):
        registry = build_inline_registry(PRIMITIVES)
        assert "next" not in registry, \
            "the dispatcher must not leak into the registry built from the full PRIMITIVES list"

    def test_registry_entries_match_direct_extraction(self):
        registry = build_inline_registry([create_dup, create_plus, create_nip])
        for creator in (create_dup, create_plus, create_nip):
            name = primitive_name(creator)
            assert registry[name] == extract_inline_body(creator), \
                f"registry entry for {name} should equal direct extraction"
