from __future__ import annotations

import pytest

from zt.compile.compiler import Compiler


def _fresh_compiler():
    return Compiler(
        origin=0x8000, optimize=False,
        inline_next=True, inline_primitives=True, include_sprites=True,
    )


class TestBlobRegistryAttachedToCompiler:

    def test_compiler_exposes_blob_registry(self):
        compiler = _fresh_compiler()
        assert hasattr(compiler, "_blob_registry"), (
            "Compiler should expose a _blob_registry attribute after registration"
        )

    def test_blob_registry_lists_match_primitives(self):
        compiler = _fresh_compiler()
        assert len(compiler._blob_registry.blobs) == len(compiler._primitives), (
            "registry should contain one blob per registered primitive creator"
        )

    def test_creators_by_name_is_unchanged_in_keyset(self):
        compiler = _fresh_compiler()
        registry_keys = set(compiler._blob_registry.forth_visible_creators())
        existing_keys = set(compiler._creators_by_name)
        assert registry_keys == existing_keys, (
            "BlobRegistry.forth_visible_creators must produce the same keyset as the "
            f"existing _creators_by_name "
            f"(missing: {existing_keys - registry_keys}; "
            f"extra: {registry_keys - existing_keys})"
        )


class TestPrimitiveEmissionUnchanged:

    def test_primitive_addresses_unchanged_after_refactor(self):
        compiler = _fresh_compiler()
        for primitive in ["dup", "drop", "swap", "+", "-", "halt", "emit", "0branch"]:
            word = compiler.words.get(primitive)
            assert word is not None, f"primitive {primitive!r} should remain registered"
            assert word.address >= 0x8000, (
                f"primitive {primitive!r} address {word.address:#x} should be at or above origin"
            )

    def test_full_primitive_image_bytes_unchanged(self):
        before = _fresh_compiler()
        before_image = bytes(before.asm.code)
        before_labels = dict(before.asm.labels)
        after = _fresh_compiler()
        after_image = bytes(after.asm.code)
        after_labels = dict(after.asm.labels)
        assert before_image == after_image, (
            "two fresh compilers should produce identical primitive image bytes"
        )
        assert before_labels == after_labels, (
            "two fresh compilers should produce identical label tables"
        )


class TestLivenessReportingApi:

    def test_compiler_can_compute_liveness_set(self):
        compiler = _fresh_compiler()
        compiler.compile_source(": main 1 2 + drop ;")
        compiler.compile_main_call()
        liveness = compiler.compute_liveness()
        assert "main" in liveness.words, (
            "main colon definition should be live"
        )
        assert "+" in liveness.words, (
            "primitives referenced from main should be live"
        )
        assert "drop" in liveness.words, (
            "primitives referenced from main should be live"
        )

    def test_unused_primitive_not_in_live_set(self):
        compiler = _fresh_compiler()
        compiler.compile_source(": main 1 2 + drop ;")
        compiler.compile_main_call()
        liveness = compiler.compute_liveness()
        assert "rot" not in liveness.words, (
            "primitive never referenced from any reachable colon should be dead"
        )
        assert "blit8" not in liveness.words, (
            "sprite primitives not referenced from main should be dead"
        )

    def test_implicit_runtime_roots_are_live(self):
        compiler = _fresh_compiler()
        compiler.compile_source(": main 1 ;")
        compiler.compile_main_call()
        liveness = compiler.compute_liveness()
        assert "next" in liveness.words, (
            "NEXT is the runtime dispatch target, should always be live"
        )
        assert "docol" in liveness.words, (
            "DOCOL is invoked by every colon, should always be live"
        )

    def test_liveness_call_does_not_modify_image(self):
        compiler = _fresh_compiler()
        compiler.compile_source(": main 1 ;")
        compiler.compile_main_call()
        before = bytes(compiler.asm.code)
        compiler.compute_liveness()
        after = bytes(compiler.asm.code)
        assert before == after, (
            "compute_liveness must not mutate the image — Phase B.2 is report-only"
        )
