from __future__ import annotations

import pytest

from zt.compile.ir import Branch, ColonRef, Label, Literal, PrimRef, StringRef, WordLiteral
from zt.compile.liveness import Liveness, compute_liveness


class TestRootsOnly:

    def test_empty_roots_yields_empty_liveness(self):
        result = compute_liveness(roots=[], bodies={}, prim_deps={})
        assert result.words == frozenset(), (
            "no roots should yield no live words"
        )
        assert result.strings == frozenset(), (
            "no roots should yield no live strings"
        )

    def test_root_with_no_body_or_deps_is_still_live(self):
        result = compute_liveness(roots=["x"], bodies={}, prim_deps={})
        assert result.words == frozenset({"x"}), (
            "a bare root with no further deps should be marked live"
        )

    def test_multiple_roots_each_kept_and_expanded(self):
        bodies = {"a": [PrimRef("dup")], "b": [PrimRef("drop")]}
        result = compute_liveness(roots=["a", "b"], bodies=bodies, prim_deps={})
        assert result.words == frozenset({"a", "b", "dup", "drop"}), (
            "every root and each root's deps should appear in the live set"
        )


class TestColonBodyTraversal:

    def test_colon_body_pulls_in_referenced_words(self):
        bodies = {"main": [ColonRef("foo"), PrimRef("dup")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert result.words == frozenset({"main", "foo", "dup"}), (
            "main referencing foo and dup should make all three live"
        )

    def test_unreferenced_colon_stays_dead(self):
        bodies = {"main": [PrimRef("dup")], "unused": [PrimRef("drop")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "unused" not in result.words, (
            "a colon not reachable from any root should stay dead"
        )
        assert "drop" not in result.words, (
            "a primitive only referenced by a dead colon should stay dead"
        )

    def test_transitive_chain_through_colons(self):
        bodies = {
            "main": [ColonRef("a")],
            "a": [ColonRef("b")],
            "b": [PrimRef("emit")],
        }
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert result.words == frozenset({"main", "a", "b", "emit"}), (
            "transitive colon-to-colon-to-primitive chain should all be live"
        )

    def test_cyclic_references_terminate_and_mark_both(self):
        bodies = {"a": [ColonRef("b")], "b": [ColonRef("a")]}
        result = compute_liveness(roots=["a"], bodies=bodies, prim_deps={})
        assert result.words == frozenset({"a", "b"}), (
            "mutual recursion between a and b should mark both live without looping"
        )


class TestCellKindContributions:

    @pytest.mark.parametrize("cell, expected_word", [
        (PrimRef("dup"), "dup"),
        (ColonRef("foo"), "foo"),
        (Literal(42), "lit"),
        (WordLiteral("foo"), "foo"),
        (Branch(kind="0branch", target=Label(0)), "0branch"),
    ])
    def test_cell_kind_contributes_word(self, cell, expected_word):
        bodies = {"main": [cell]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert expected_word in result.words, (
            f"{type(cell).__name__} should make {expected_word!r} live"
        )

    def test_string_ref_collected_in_strings_not_words(self):
        bodies = {"main": [StringRef("S0")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "S0" in result.strings, (
            "StringRef should add label to live strings"
        )
        assert "S0" not in result.words, (
            "StringRef labels should not pollute the live word set"
        )

    def test_label_cell_contributes_nothing(self):
        bodies = {"main": [Label(id=0), PrimRef("dup")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert result.words == frozenset({"main", "dup"}), (
            "Label cells should contribute neither words nor strings"
        )

    def test_literal_zero_still_pulls_in_lit(self):
        bodies = {"main": [Literal(0)]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "lit" in result.words, (
            "even a zero Literal should keep the 'lit' primitive live"
        )


class TestWordLiteralContribution:

    def test_word_literal_pulls_in_lit_primitive(self):
        bodies = {"main": [WordLiteral("isr")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "lit" in result.words, (
            "WordLiteral compiles to LIT+addr at runtime, so 'lit' must be live"
        )

    def test_word_literal_marks_referenced_word_live(self):
        bodies = {"main": [WordLiteral("isr")], "isr": [PrimRef("exit")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "isr" in result.words, (
            "WordLiteral('isr') should make 'isr' live just like a direct call would"
        )

    def test_word_literal_pulls_in_referenced_word_transitively(self):
        bodies = {
            "main": [WordLiteral("isr")],
            "isr": [PrimRef("border"), ColonRef("helper")],
            "helper": [PrimRef("dup")],
        }
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert {"main", "isr", "helper", "border", "dup", "lit"} <= result.words, (
            "WordLiteral target's transitive deps should all be live"
        )

    def test_unreferenced_word_only_used_via_dead_word_literal_stays_dead(self):
        bodies = {
            "main": [PrimRef("dup")],
            "dead": [WordLiteral("orphan")],
            "orphan": [PrimRef("emit")],
        }
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "orphan" not in result.words, (
            "'orphan' reached only through a dead-word's WordLiteral should stay dead"
        )


class TestDataRefs:

    def test_data_ref_pulls_target_when_owner_is_live(self):
        bodies = {"main": [ColonRef("frames")]}
        data_refs = {"frames": ["smiley-shifted"]}
        result = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs=data_refs,
        )
        assert "smiley-shifted" in result.words, (
            "data ref from a live owner should pull its target into the live set"
        )

    def test_data_ref_target_is_dead_when_owner_is_dead(self):
        bodies = {"main": [PrimRef("dup")]}
        data_refs = {"unused-frames": ["unused-shifted"]}
        result = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs=data_refs,
        )
        assert "unused-shifted" not in result.words, (
            "data ref from a dead owner should not resurrect its target"
        )
        assert "unused-frames" not in result.words, (
            "the dead owner itself stays dead"
        )

    def test_data_ref_target_walked_transitively(self):
        bodies = {
            "main": [ColonRef("frames")],
            "smiley-shifted": [PrimRef("emit"), ColonRef("inner")],
            "inner": [PrimRef("dup")],
        }
        data_refs = {"frames": ["smiley-shifted"]}
        result = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs=data_refs,
        )
        assert {"frames", "smiley-shifted", "emit", "inner", "dup"} <= result.words, (
            "transitive deps of a data-ref target should all be live"
        )

    def test_owner_with_no_data_refs_in_mapping_works(self):
        bodies = {"main": [ColonRef("frames")]}
        result = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs={},
        )
        assert "frames" in result.words, (
            "absent data_refs should not break liveness for words without refs"
        )

    def test_data_refs_default_to_empty_when_omitted(self):
        bodies = {"main": [ColonRef("frames")]}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps={})
        assert "frames" in result.words, (
            "data_refs should be optional; omitting it should match passing {}"
        )

    def test_two_targets_from_one_owner_both_kept(self):
        bodies = {"main": [ColonRef("table")]}
        data_refs = {"table": ["a", "b"]}
        result = compute_liveness(
            roots=["main"], bodies=bodies, prim_deps={}, data_refs=data_refs,
        )
        assert {"a", "b"} <= result.words, (
            "every target listed for a live owner should be live"
        )


class TestPrimitiveDepGraph:

    def test_primitive_deps_walked_transitively(self):
        prim_deps = {
            "emit": ["next", "rom_print"],
            "next": [],
            "rom_print": [],
        }
        result = compute_liveness(roots=["emit"], bodies={}, prim_deps=prim_deps)
        assert result.words == frozenset({"emit", "next", "rom_print"}), (
            "primitive deps should be transitively closed from a root primitive"
        )

    def test_primitive_pulled_from_colon_drags_its_deps(self):
        bodies = {"main": [PrimRef("emit")]}
        prim_deps = {"emit": ["next"], "next": []}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps=prim_deps)
        assert result.words == frozenset({"main", "emit", "next"}), (
            "a primitive referenced from a colon should drag in its primitive deps"
        )

    def test_primitive_only_reachable_via_dead_colon_stays_dead(self):
        bodies = {"main": [], "dead": [PrimRef("emit")]}
        prim_deps = {"emit": ["next"], "next": []}
        result = compute_liveness(roots=["main"], bodies=bodies, prim_deps=prim_deps)
        assert "emit" not in result.words, (
            "primitive ref'd only from an unreachable colon should not be marked live"
        )
        assert "next" not in result.words, (
            "transitive primitive of an unreachable primitive should also stay dead"
        )

    def test_primitive_dep_cycle_terminates(self):
        prim_deps = {"a": ["b"], "b": ["a"]}
        result = compute_liveness(roots=["a"], bodies={}, prim_deps=prim_deps)
        assert result.words == frozenset({"a", "b"}), (
            "a cycle between primitives should mark both without looping forever"
        )


class TestApiShape:

    def test_returns_liveness_instance(self):
        result = compute_liveness(roots=[], bodies={}, prim_deps={})
        assert isinstance(result, Liveness), (
            "compute_liveness should return a Liveness instance"
        )

    def test_liveness_fields_are_frozensets(self):
        result = compute_liveness(roots=["x"], bodies={}, prim_deps={})
        assert isinstance(result.words, frozenset), (
            "Liveness.words should be a frozenset for hashable, immutable use"
        )
        assert isinstance(result.strings, frozenset), (
            "Liveness.strings should be a frozenset for hashable, immutable use"
        )

    def test_inputs_not_mutated(self):
        bodies = {"main": [PrimRef("dup")]}
        prim_deps = {"dup": []}
        roots = ["main"]
        compute_liveness(roots=roots, bodies=bodies, prim_deps=prim_deps)
        assert bodies == {"main": [PrimRef("dup")]}, (
            "compute_liveness should not mutate the bodies argument"
        )
        assert prim_deps == {"dup": []}, (
            "compute_liveness should not mutate the prim_deps argument"
        )
        assert roots == ["main"], (
            "compute_liveness should not mutate the roots iterable"
        )
