"""
Tests for the `Dictionary` symbol table: register/lookup, primitive seeding, redefinition warnings, and iteration.
"""
import pytest

from zt.asm import Asm
from zt.compiler import Word
from zt.dictionary import Dictionary
from zt.primitives import PRIMITIVES


@pytest.fixture
def dictionary() -> Dictionary:
    return Dictionary()


class TestRegisterAndLookup:

    def test_empty_dictionary_has_no_words(self, dictionary):
        assert len(dictionary) == 0, "new Dictionary should be empty"

    def test_register_stores_word(self, dictionary):
        w = Word(name="dup", address=0x1000, kind="prim")
        dictionary.register(w)
        assert dictionary["dup"] is w, "register should store the Word under its name"

    def test_get_returns_none_for_unknown(self, dictionary):
        assert dictionary.get("missing") is None, (
            "get should return None for an unknown name"
        )

    def test_subscript_raises_for_unknown(self, dictionary):
        with pytest.raises(KeyError):
            _ = dictionary["missing"]

    def test_contains_returns_true_for_registered(self, dictionary):
        dictionary.register(Word(name="dup", address=0x1000, kind="prim"))
        assert "dup" in dictionary, "__contains__ should return True after register"
        assert "missing" not in dictionary, "__contains__ should return False for unknown"


class TestPrimitives:

    def test_register_primitives_populates_from_asm_labels(self, dictionary):
        asm = Asm(0x8000, inline_next=False)
        for creator in PRIMITIVES:
            creator(asm)
        dictionary.register_primitives(asm)
        assert "dup" in dictionary, "register_primitives should discover 'dup'"
        assert dictionary["dup"].kind == "prim", "discovered words should be kind 'prim'"

    def test_register_primitives_skips_underscore_labels(self, dictionary):
        asm = Asm(0x8000, inline_next=False)
        asm.label("_internal")
        asm.label("PUBLIC")
        asm.byte(0)
        dictionary.register_primitives(asm)
        assert "_internal" not in dictionary, (
            "register_primitives should skip labels starting with underscore"
        )
        assert "public" in dictionary, (
            "register_primitives should register non-underscore labels (lowercased)"
        )

    def test_register_primitives_does_not_overwrite_existing(self, dictionary):
        existing = Word(name="dup", address=0x0001, kind="colon")
        dictionary.register(existing)
        asm = Asm(0x8000, inline_next=False)
        for creator in PRIMITIVES:
            creator(asm)
        dictionary.register_primitives(asm)
        assert dictionary["dup"] is existing, (
            "register_primitives must not overwrite a pre-existing Word with the same name"
        )


class TestRedefinitionWarning:

    def test_no_warning_for_first_definition(self, dictionary):
        warning = dictionary.redefinition_warning(
            "double", source_file="a.fs", source_line=3,
        )
        assert warning is None, "no warning should fire on first definition"

    def test_warning_when_redefining_colon(self, dictionary):
        dictionary.register(Word(
            name="double", address=0x8100, kind="colon",
            source_file="a.fs", source_line=1,
        ))
        warning = dictionary.redefinition_warning(
            "double", source_file="b.fs", source_line=7,
        )
        assert warning is not None, "redefining a colon word should yield a warning"
        assert "double" in warning and "a.fs" in warning and "b.fs" in warning, (
            "warning should mention word name plus both source locations"
        )

    def test_no_warning_when_previous_is_primitive(self, dictionary):
        dictionary.register(Word(name="dup", address=0x1000, kind="prim"))
        warning = dictionary.redefinition_warning(
            "dup", source_file="a.fs", source_line=1,
        )
        assert warning is None, (
            "redefining a primitive (intentional override) should not produce a warning"
        )

    def test_no_warning_when_previous_has_no_source(self, dictionary):
        dictionary.register(Word(
            name="double", address=0x8100, kind="colon",
            source_file=None, source_line=None,
        ))
        warning = dictionary.redefinition_warning(
            "double", source_file="b.fs", source_line=7,
        )
        assert warning is None, (
            "no warning when the previous definition has no recorded source location"
        )


class TestIterationAndValues:

    def test_items_returns_name_word_pairs(self, dictionary):
        w = Word(name="dup", address=0x1000, kind="prim")
        dictionary.register(w)
        items = list(dictionary.items())
        assert items == [("dup", w)], "items should yield (name, Word) pairs"

    def test_values_yields_registered_words(self, dictionary):
        w1 = Word(name="a", address=0x1000, kind="prim")
        w2 = Word(name="b", address=0x2000, kind="colon")
        dictionary.register(w1)
        dictionary.register(w2)
        assert list(dictionary.values()) == [w1, w2], (
            "values should yield registered Words in insertion order"
        )
