from __future__ import annotations

import pytest

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import emit_blob, harvest_primitive


def _splat_via_blob(creators, *, origin=0x8000, inline_next=True):
    asm = Asm(origin=origin, inline_next=inline_next)
    for c in creators:
        emit_blob(asm, harvest_primitive(c, inline_next=inline_next))
    return asm


def _splat_via_eager(creators, *, origin=0x8000, inline_next=True):
    asm = Asm(origin=origin, inline_next=inline_next)
    for c in creators:
        c(asm)
    return asm


class TestEmitBlobByteIdentity:

    def test_single_blob_emits_same_bytes_as_eager(self):
        from zt.assemble.primitives import create_dup
        blob_asm = _splat_via_blob([create_dup])
        eager_asm = _splat_via_eager([create_dup])
        assert blob_asm.code == eager_asm.code, (
            "emit_blob of a single creator should produce identical bytes to creator(asm)"
        )

    @pytest.mark.parametrize("creator_name", [
        "create_dup", "create_drop", "create_swap", "create_over",
        "create_zero", "create_zbranch",
    ])
    def test_each_simple_primitive_byte_identical(self, creator_name):
        from zt.assemble import primitives as P
        creator = getattr(P, creator_name)
        blob_asm = _splat_via_blob([creator])
        eager_asm = _splat_via_eager([creator])
        assert blob_asm.code == eager_asm.code, (
            f"{creator_name} should be byte-identical via emit_blob and direct call"
        )

    def test_full_primitive_set_byte_identical_after_resolve(self):
        from zt.assemble.primitives import PRIMITIVES
        blob_asm = _splat_via_blob(PRIMITIVES)
        eager_asm = _splat_via_eager(PRIMITIVES)
        assert blob_asm.code == eager_asm.code, (
            "full PRIMITIVES sequence should produce identical pre-resolve code"
        )
        assert blob_asm.resolve() == eager_asm.resolve(), (
            "full PRIMITIVES sequence should produce identical post-resolve bytes"
        )


class TestEmitBlobLabels:

    def test_label_address_includes_origin_and_offset(self):
        from zt.assemble.primitives import create_dup, create_drop
        asm = _splat_via_blob([create_dup, create_drop], origin=0x9000)
        assert asm.labels["DUP"] == 0x9000, (
            "first blob's label should be at origin"
        )
        eager = _splat_via_eager([create_dup, create_drop], origin=0x9000)
        assert asm.labels["DROP"] == eager.labels["DROP"], (
            "second blob's label should match what eager emission produces"
        )

    def test_aliases_bind_to_same_address_as_canonical(self):
        from zt.assemble.primitives import create_dup
        asm = _splat_via_blob([create_dup], origin=0x9000)
        assert asm.labels["dup"] == asm.labels["DUP"], (
            "alias and canonical label should resolve to identical addresses"
        )


class TestEmitBlobFixupOffsets:

    def test_external_jp_target_resolves_via_later_blob(self):
        from zt.assemble.primitives import create_next, create_dup
        asm = _splat_via_blob([create_next, create_dup], inline_next=False, origin=0x8000)
        eager = _splat_via_eager([create_next, create_dup], inline_next=False, origin=0x8000)
        assert asm.resolve() == eager.resolve(), (
            "blob emission with inline_next=False should still resolve identical to eager"
        )

    def test_emit_blob_does_not_mutate_blob(self):
        from zt.assemble.primitives import create_dup
        blob = harvest_primitive(create_dup)
        original_code = blob.code
        original_fixups = blob.fixups
        original_label_offsets = dict(blob.label_offsets)
        asm = Asm(origin=0x8000)
        emit_blob(asm, blob)
        assert blob.code == original_code, (
            "blob.code should not change after emit_blob"
        )
        assert blob.fixups == original_fixups, (
            "blob.fixups should not change after emit_blob"
        )
        assert dict(blob.label_offsets) == original_label_offsets, (
            "blob.label_offsets should not change after emit_blob"
        )


class TestEmitBlobDuplicates:

    def test_emitting_same_blob_twice_raises_on_label_collision(self):
        from zt.assemble.primitives import create_dup
        blob = harvest_primitive(create_dup)
        asm = Asm(origin=0x8000)
        emit_blob(asm, blob)
        with pytest.raises(ValueError, match="duplicate label"):
            emit_blob(asm, blob)
