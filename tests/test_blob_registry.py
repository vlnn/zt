from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import (
    BlobRegistry,
    PrimitiveBlob,
    harvest_primitive,
)


def _two_simple_creators():
    from zt.assemble.primitives import create_dup, create_drop
    return [create_dup, create_drop]


class TestRegistryConstruction:

    def test_from_creators_returns_registry_instance(self):
        registry = BlobRegistry.from_creators(_two_simple_creators())
        assert isinstance(registry, BlobRegistry), (
            "from_creators should return a BlobRegistry"
        )

    def test_blobs_match_creator_count(self):
        creators = _two_simple_creators()
        registry = BlobRegistry.from_creators(creators)
        assert len(registry.blobs) == len(creators), (
            "registry should expose one blob per input creator"
        )

    def test_blobs_in_registration_order(self):
        from zt.assemble.primitives import create_dup, create_drop, create_swap
        registry = BlobRegistry.from_creators([create_dup, create_drop, create_swap])
        first_label = next(iter(registry.blobs[0].label_offsets))
        last_label = next(iter(registry.blobs[-1].label_offsets))
        assert first_label == "DUP", "first blob should correspond to first creator"
        assert last_label == "SWAP", "last blob should correspond to last creator"

    def test_inline_next_propagates_to_blobs(self):
        from zt.assemble.primitives import create_dup
        inline = BlobRegistry.from_creators([create_dup], inline_next=True)
        plain = BlobRegistry.from_creators([create_dup], inline_next=False)
        assert inline.blobs[0].external_deps == frozenset(), (
            "inline_next=True should suppress NEXT dep"
        )
        assert plain.blobs[0].external_deps == frozenset({"NEXT"}), (
            "inline_next=False should expose NEXT dep"
        )


class TestForthVisibleCreators:

    def test_lowercases_label_names(self):
        from zt.assemble.primitives import create_dup
        registry = BlobRegistry.from_creators([create_dup])
        creators = registry.forth_visible_creators()
        assert "dup" in creators, "DUP and its alias should both map under lowercase 'dup'"

    def test_excludes_NEXT_label(self):
        from zt.assemble.primitives import create_next, create_dup
        registry = BlobRegistry.from_creators([create_next, create_dup])
        creators = registry.forth_visible_creators()
        assert "next" not in creators, "NEXT should be excluded from Forth-visible creators"

    def test_excludes_underscore_prefixed_labels(self):
        from zt.assemble.primitives import create_zbranch
        registry = BlobRegistry.from_creators([create_zbranch])
        creators = registry.forth_visible_creators()
        assert all(not name.startswith("_") for name in creators), (
            "underscore-prefixed labels should not appear as Forth-visible names"
        )

    def test_excludes_creators_with_unsatisfied_external_deps(self):
        from zt.assemble.primitives import create_at_xy
        registry = BlobRegistry.from_creators([create_at_xy])
        creators = registry.forth_visible_creators()
        assert "at-xy" not in creators, (
            "primitive whose external deps are unsatisfied (e.g. _emit_cursor_row) "
            "should be excluded — matches existing _build_creators_by_name behavior"
        )
        assert "at_xy" not in creators, (
            "snake-case alias should also be excluded for the same reason"
        )

    def test_includes_creator_when_external_dep_only_NEXT(self):
        from zt.assemble.primitives import create_dup
        registry = BlobRegistry.from_creators([create_dup], inline_next=False)
        creators = registry.forth_visible_creators()
        assert "dup" in creators, (
            "primitive whose only external dep is NEXT should be included "
            "(NEXT is implicitly available)"
        )

    def test_real_primitive_set_matches_existing_creators_by_name(self):
        from zt.compile.compiler import Compiler
        from zt.assemble.primitives import PRIMITIVES
        compiler = Compiler(
            origin=0x8000, optimize=False,
            inline_next=True, inline_primitives=True,
        )
        registry = BlobRegistry.from_creators(PRIMITIVES, inline_next=True)
        new_keys = set(registry.forth_visible_creators())
        old_keys = set(compiler._creators_by_name)
        assert new_keys == old_keys, (
            "BlobRegistry.forth_visible_creators should return exactly the same "
            f"key set as Compiler._build_creators_by_name "
            f"(missing in new: {old_keys - new_keys}; "
            f"extra in new: {new_keys - old_keys})"
        )

    def test_returned_value_per_key_is_the_input_creator(self):
        from zt.assemble.primitives import create_dup, create_drop
        creators = [create_dup, create_drop]
        registry = BlobRegistry.from_creators(creators)
        result = registry.forth_visible_creators()
        assert result["dup"] is create_dup, (
            "lowercase 'dup' should map to the create_dup function object itself"
        )
        assert result["drop"] is create_drop, (
            "lowercase 'drop' should map to the create_drop function object itself"
        )


class TestRegistryByLabel:

    def test_by_label_lookup_returns_blob_for_canonical(self):
        registry = BlobRegistry.from_creators(_two_simple_creators())
        dup_blob = registry.by_label("DUP")
        assert dup_blob is registry.blobs[0], (
            "by_label('DUP') should return the same blob as registry.blobs[0]"
        )

    def test_by_label_lookup_returns_same_blob_for_alias(self):
        registry = BlobRegistry.from_creators(_two_simple_creators())
        assert registry.by_label("dup") is registry.by_label("DUP"), (
            "an alias should resolve to the same blob as its canonical label"
        )

    def test_by_label_raises_for_unknown_name(self):
        registry = BlobRegistry.from_creators(_two_simple_creators())
        with pytest.raises(KeyError):
            registry.by_label("not_a_real_primitive")


class TestRegistryDependencyGraph:

    def test_graph_has_entries_for_every_label(self):
        from zt.assemble.primitives import create_dup, create_drop
        registry = BlobRegistry.from_creators([create_dup, create_drop])
        graph = registry.dependency_graph()
        for label_name in ("DUP", "dup", "DROP", "drop"):
            assert label_name in graph, (
                f"every blob label including aliases should appear in dependency graph; "
                f"missing: {label_name!r}"
            )

    def test_graph_entries_match_blob_external_deps(self):
        from zt.assemble.primitives import create_at_xy
        registry = BlobRegistry.from_creators([create_at_xy])
        graph = registry.dependency_graph()
        assert graph["AT_XY"] == registry.blobs[0].external_deps, (
            "graph entry should equal the blob's external_deps"
        )
