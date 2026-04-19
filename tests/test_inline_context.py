"""
Tests for `InlineContext.build` and the primitive-name-to-key mapping it derives from `PRIMITIVES`.
"""
from __future__ import annotations

import pytest

from zt.assemble.inline_bodies import InlineContext, is_primitive_inlinable
from zt.assemble.primitives import PRIMITIVES


@pytest.fixture(scope="module")
def context() -> InlineContext:
    return InlineContext.build(PRIMITIVES)


class TestContextBuild:

    def test_registry_contains_dup_bytes(self, context):
        assert "dup" in context.registry, \
            "a context built from PRIMITIVES should register 'dup'"
        assert len(context.registry["dup"]) > 0, \
            "the registered body for 'dup' should have at least one byte"

    def test_name_to_key_maps_dup_to_itself(self, context):
        assert context.name_to_key.get("dup") == "dup", \
            "the canonical primitive 'dup' should map to key 'dup'"


class TestNameToKeyFromPythonName:

    @pytest.mark.parametrize("forth_name,expected_key", [
        ("dup",       "dup"),
        ("drop",      "drop"),
        ("swap",      "swap"),
        ("over",      "over"),
        ("nip",       "nip"),
        ("rot",       "rot"),
    ])
    def test_lowercase_forth_name_maps_to_stripped_python_name(
        self, context, forth_name, expected_key,
    ):
        assert context.name_to_key.get(forth_name) == expected_key, \
            f"{forth_name!r} should resolve to registry key {expected_key!r}"


class TestNameToKeyFromSymbolicAlias:

    @pytest.mark.parametrize("forth_name,expected_key", [
        ("+",     "plus"),
        ("-",     "minus"),
        ("1+",    "one_plus"),
        ("1-",    "one_minus"),
        ("2*",    "two_star"),
        ("2/",    "two_slash"),
        ("@",     "fetch"),
        ("!",     "store"),
        ("c@",    "c_fetch"),
        ("c!",    "c_store"),
        ("+!",    "plus_store"),
        ("dup@",  "dup_fetch"),
    ])
    def test_symbolic_alias_resolves_to_python_name_key(
        self, context, forth_name, expected_key,
    ):
        assert context.name_to_key.get(forth_name) == expected_key, \
            f"symbolic alias {forth_name!r} should map to {expected_key!r}"


class TestNameToKeyUppercaseAlias:

    @pytest.mark.parametrize("uppercase_name,expected_key", [
        ("PLUS",    "plus"),
        ("DUP",     "dup"),
        ("DROP",    "drop"),
        ("SWAP",    "swap"),
        ("FETCH",   "fetch"),
        ("STORE",   "store"),
    ])
    def test_uppercase_primary_label_also_resolves(
        self, context, uppercase_name, expected_key,
    ):
        assert context.name_to_key.get(uppercase_name.lower()) == expected_key, \
            f"{uppercase_name!r} (lowercased) should resolve to {expected_key!r}"

    def test_primitives_without_uppercase_alias_still_resolve_by_forth_name(
        self, context,
    ):
        assert context.name_to_key.get("1+") == "one_plus", \
            "primitives like 1+ have no uppercase alias; the Forth name is the only label"
        assert context.name_to_key.get("one_plus") is None, \
            "one_plus (the Python registry key) is not a Forth label and should not resolve"


class TestNameToKeyForNonInlinablePrimitives:

    @pytest.mark.parametrize("forth_name,expected_key", [
        ("<",  "less_than"),
        (">",  "greater_than"),
    ])
    def test_non_inlinable_primitives_are_still_mapped(
        self, context, forth_name, expected_key,
    ):
        key = context.name_to_key.get(forth_name)
        assert key == expected_key, \
            f"{forth_name!r} should resolve to its registry key even if non-inlinable"
        assert not is_primitive_inlinable(key), \
            f"{expected_key!r} must not be in the inlinable whitelist; " \
            "gatekeeping happens in is_primitive_inlinable, not via name_to_key absence"


class TestNameToKeyForDispatcherAndHalt:

    def test_dispatcher_label_is_not_in_map(self, context):
        assert "next" not in context.name_to_key, \
            "the NEXT dispatcher must never appear in name_to_key"

    def test_halt_is_not_in_map(self, context):
        assert "halt" not in context.name_to_key, \
            "halt has no dispatch tail and must not appear in name_to_key"
