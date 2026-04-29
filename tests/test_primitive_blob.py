from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import (
    PrimitiveBlob,
    harvest_primitive,
    harvest_primitives,
    primitive_dependency_graph,
)


def _make_label_then_jp(label_name: str, jp_target: str):
    def creator(a: Asm) -> None:
        a.label(label_name)
        a.jp(jp_target)
    return creator


def _make_self_loop(label_name: str):
    def creator(a: Asm) -> None:
        a.label(label_name)
        a.nop()
        a.jp(label_name)
    return creator


class TestHarvestPrimitiveBasics:

    def test_returns_primitive_blob_instance(self):
        blob = harvest_primitive(_make_label_then_jp("FOO", "BAR"))
        assert isinstance(blob, PrimitiveBlob), (
            "harvest_primitive should return a PrimitiveBlob"
        )

    def test_label_recorded_at_offset_zero(self):
        blob = harvest_primitive(_make_label_then_jp("FOO", "BAR"))
        assert blob.label_offsets["FOO"] == 0, (
            "first label should be at offset 0 within the blob"
        )

    def test_emits_at_least_one_byte_for_nontrivial_creator(self):
        blob = harvest_primitive(_make_label_then_jp("FOO", "BAR"))
        assert len(blob.code) > 0, (
            "creator that emits a JP should produce non-empty code"
        )

    def test_pure_label_only_creator_emits_zero_bytes(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
        blob = harvest_primitive(creator)
        assert blob.code == b"", (
            "a creator that only declares a label should emit no bytes"
        )


class TestExternalDeps:

    def test_external_jp_target_appears_in_external_deps(self):
        blob = harvest_primitive(_make_label_then_jp("FOO", "BAR"))
        assert "BAR" in blob.external_deps, (
            "an external JP target should appear in external_deps"
        )

    def test_self_label_does_not_appear_in_external_deps(self):
        blob = harvest_primitive(_make_self_loop("FOO"))
        assert "FOO" not in blob.external_deps, (
            "a JP back to a label declared in this blob is internal, not external"
        )

    def test_alias_does_not_appear_in_external_deps(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.alias("foo", "FOO")
            a.jp("foo")
        blob = harvest_primitive(creator)
        assert blob.external_deps == frozenset(), (
            "JP to an alias of a self-label should not produce an external dep"
        )

    def test_relative_jump_target_also_collected(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.jr_to("BAR")
        blob = harvest_primitive(creator)
        assert "BAR" in blob.external_deps, (
            "relative jumps to external labels should also appear in external_deps"
        )

    def test_internal_relative_jump_is_not_external(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.nop()
            a.jr_to("FOO")
        blob = harvest_primitive(creator)
        assert blob.external_deps == frozenset(), (
            "relative jumps inside the same blob should not appear in external_deps"
        )


class TestRealPrimitiveShapes:

    def test_dup_with_inline_next_has_no_external_deps(self):
        from zt.assemble.primitives import create_dup
        blob = harvest_primitive(create_dup, inline_next=True)
        assert blob.external_deps == frozenset(), (
            "with inline_next=True, dup inlines NEXT body and has no external deps"
        )

    def test_dup_without_inline_next_depends_on_NEXT(self):
        from zt.assemble.primitives import create_dup
        blob = harvest_primitive(create_dup, inline_next=False)
        assert blob.external_deps == frozenset({"NEXT"}), (
            "with inline_next=False, dup ends in JP NEXT and has NEXT as its only dep"
        )

    def test_dup_canonical_and_alias_both_at_offset_zero(self):
        from zt.assemble.primitives import create_dup
        blob = harvest_primitive(create_dup)
        assert blob.label_offsets["DUP"] == 0, (
            "DUP canonical label should be at offset 0"
        )
        assert blob.label_offsets["dup"] == 0, (
            "dup alias should be at the same offset as DUP"
        )

    def test_zbranch_internal_skip_label_is_self_not_external(self):
        from zt.assemble.primitives import create_zbranch
        blob = harvest_primitive(create_zbranch, inline_next=True)
        assert "_zbranch_skip" not in blob.external_deps, (
            "0branch's internal _zbranch_skip label should not appear as external"
        )

    def test_next_is_a_leaf(self):
        from zt.assemble.primitives import create_next
        for inline_next in (True, False):
            blob = harvest_primitive(create_next, inline_next=inline_next)
            assert blob.external_deps == frozenset(), (
                f"NEXT should be a leaf primitive regardless of inline_next "
                f"(failed for inline_next={inline_next})"
            )


class TestFixupOffsets:

    def test_fixup_offsets_are_relative_to_blob_start(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.nop()
            a.jp("BAR")
        blob = harvest_primitive(creator)
        bar_fixups = [off for off, name in blob.fixups if name == "BAR"]
        assert bar_fixups == [2], (
            "JP after one NOP should record a 16-bit fixup at offset 2 "
            "(byte 0 = NOP, byte 1 = JP opcode, bytes 2-3 = address operand)"
        )

    def test_rel_fixup_offsets_are_relative_to_blob_start(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.nop()
            a.jr_to("BAR")
        blob = harvest_primitive(creator)
        bar_rel_fixups = [off for off, name in blob.rel_fixups if name == "BAR"]
        assert bar_rel_fixups == [2], (
            "JR after one NOP should record a 1-byte rel-fixup at offset 2"
        )


class TestPrimitiveDependencyGraph:

    def test_each_label_maps_to_its_blobs_external_deps(self):
        blobs = [harvest_primitive(_make_label_then_jp("FOO", "BAR"))]
        graph = primitive_dependency_graph(blobs)
        assert graph["FOO"] == frozenset({"BAR"}), (
            "graph entry for FOO should expose its external deps"
        )

    def test_alias_shares_external_deps_of_canonical(self):
        def creator(a: Asm) -> None:
            a.label("FOO")
            a.alias("foo", "FOO")
            a.jp("BAR")
        graph = primitive_dependency_graph([harvest_primitive(creator)])
        assert graph["FOO"] == graph["foo"] == frozenset({"BAR"}), (
            "an alias should expose the same external deps as its canonical label"
        )

    def test_combines_multiple_blobs_into_one_graph(self):
        blobs = [
            harvest_primitive(_make_label_then_jp("A", "X")),
            harvest_primitive(_make_label_then_jp("B", "Y")),
        ]
        graph = primitive_dependency_graph(blobs)
        assert graph == {
            "A": frozenset({"X"}),
            "B": frozenset({"Y"}),
        }, "each blob should contribute one entry per declared label"

    def test_real_primitive_graph_includes_dup_with_no_deps(self):
        from zt.assemble.primitives import create_dup, create_drop
        blobs = harvest_primitives(
            [create_dup, create_drop], inline_next=True,
        )
        graph = primitive_dependency_graph(blobs)
        assert graph["dup"] == frozenset(), (
            "dup with inline_next should map to empty deps in the graph"
        )
        assert graph["drop"] == frozenset(), (
            "drop with inline_next should map to empty deps in the graph"
        )


class TestHarvestPrimitivesPlural:

    def test_returns_one_blob_per_creator_in_order(self):
        creators = [
            _make_label_then_jp("A", "X"),
            _make_label_then_jp("B", "Y"),
            _make_label_then_jp("C", "Z"),
        ]
        blobs = harvest_primitives(creators)
        assert len(blobs) == 3, "should produce one blob per creator"
        assert [next(iter(b.label_offsets)) for b in blobs] == ["A", "B", "C"], (
            "blobs should be returned in the same order as the input creators"
        )

    def test_passes_inline_next_through(self):
        from zt.assemble.primitives import create_dup
        inline_blob = harvest_primitives([create_dup], inline_next=True)[0]
        plain_blob = harvest_primitives([create_dup], inline_next=False)[0]
        assert inline_blob.external_deps == frozenset(), (
            "inline_next=True should suppress NEXT dep from harvest_primitives"
        )
        assert plain_blob.external_deps == frozenset({"NEXT"}), (
            "inline_next=False should expose NEXT dep from harvest_primitives"
        )
