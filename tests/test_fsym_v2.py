"""
Tests for the fsym v2 schema (body cells + string labels), the v2 inspect path, and backward compatibility with v1 dumps.
"""
import pytest

from zt.compile.compiler import Compiler
from zt.inspect.fsym import FSYM_VERSION, to_dict
from zt.inspect.decompile import decompile


def _compile_and_dump(source: str, with_image: bool = False):
    c = Compiler()
    c.compile_source(source)
    if "main" in c.words:
        c.compile_main_call()
    image = c.build() if with_image else None
    return to_dict(c), image, c


def _strip_to_v1(fsym_dict: dict) -> dict:
    result = {"origin": fsym_dict["origin"], "words": {}}
    for name, info in fsym_dict["words"].items():
        stripped = {k: v for k, v in info.items() if k != "cells"}
        result["words"][name] = stripped
    return result


class TestFsymV2Schema:

    def test_dict_includes_fsym_version(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        assert d.get("fsym_version") == FSYM_VERSION, (
            "fsym dict should include fsym_version key for schema v2"
        )

    def test_colon_word_has_cells_field(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        cells = d["words"]["double"].get("cells")
        assert isinstance(cells, list) and cells, (
            "colon word should serialize a non-empty cells list in v2"
        )

    def test_cells_contain_prim_entries_for_primitives(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        cells = d["words"]["double"]["cells"]
        cell_shapes = [c[0] for c in cells]
        assert cell_shapes[0] == "prim", (
            "first cell of 'double' should be a primitive reference (dup)"
        )

    def test_primitive_has_no_cells_field(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        assert "cells" not in d["words"]["dup"], (
            "primitive word without a body should not have a cells field"
        )

    def test_body_field_is_not_written_in_v2(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        assert "body" not in d["words"]["double"], (
            "v2 fsym should not duplicate data in a legacy body field when cells is authoritative"
        )


class TestInspectV2Path:

    def test_inspect_uses_cells_when_present(self):
        d, _, _ = _compile_and_dump(": double dup + ;\n")
        out = decompile(d)
        assert "dup" in out and "+" in out, (
            "inspect should render primitives from the cells field"
        )

    @pytest.mark.parametrize("source", [
        ": double dup + ;\n",
        ": conditional dup if drop then ;\n",
        ": branched dup if drop else dup then ;\n",
        ": forever begin dup again ;\n",
        ": count 3 0 do i drop loop ;\n",
        ": repeater begin 1- dup 0= until drop ;\n",
    ])
    def test_control_flow_renders_without_image(self, source):
        d, _, _ = _compile_and_dump(source)
        out = decompile(d)
        assert out, f"decompile of {source!r} should produce non-empty output"

    def test_dot_quote_renders_with_image(self):
        d, image, _ = _compile_and_dump(
            ': main ." hi" halt ;\n', with_image=True,
        )
        out = decompile(d, image=image)
        assert '." hi"' in out, (
            'decompile with image should render ." hi" from the cells'
        )


class TestFsymBackwardCompat:

    def test_legacy_v1_fsym_with_resolved_body_still_decompiles(self):
        dup_addr = 0x802c
        plus_addr = 0x8180
        exit_addr = 0x801c
        legacy = {
            "origin": 0x8000,
            "words": {
                "double": {
                    "address": 0x8400, "kind": "colon",
                    "body": [dup_addr, plus_addr, exit_addr],
                },
                "dup": {"address": dup_addr, "kind": "prim"},
                "+": {"address": plus_addr, "kind": "prim"},
                "exit": {"address": exit_addr, "kind": "prim"},
            },
        }
        out = decompile(legacy)
        assert "dup" in out and "+" in out, (
            "legacy v1 fsym (with resolved int body, no cells) should still decompile"
        )
