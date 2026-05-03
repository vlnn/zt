"""
Structural and behavioural tests for the structs example.

Verifies that the example compiles, defines the expected words, fuses the
expected access patterns at the expected sites, and produces the expected
final HP values when run through the simulator for one combat round.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler
from zt.compile.ir import (
    NativeFetch,
    NativeStore,
    NativeOffsetFetch,
    NativeOffsetStore,
)
from zt.sim import Z80, _read_data_stack


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"
APP = EXAMPLE_DIR / "app" / "menagerie.fs"


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestFiles:

    @pytest.mark.parametrize("relpath", ["main.fs", "app/menagerie.fs"])
    def test_example_files_exist(self, relpath):
        assert (EXAMPLE_DIR / relpath).is_file(), (
            f"{relpath} should exist in the structs example"
        )


class TestCompiles:

    def test_main_word_is_defined(self, built_compiler):
        assert "main" in built_compiler.words, (
            "structs example should produce a 'main' word"
        )

    @pytest.mark.parametrize("word", [
        ".x", ".y", ".hp", ".mp", ".rage",
        "/actor", "/boss",
        "hero", "goblin", "troll",
        "actor-x", "actor-y", "actor-hp", "actor-mp", "boss-rage",
        "set-actor-x", "set-actor-y", "set-actor-hp", "set-boss-rage",
        "take-damage",
        "setup-actors", "fight-one-round", "print-results",
    ])
    def test_expected_word_is_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"structs example should define {word!r}"
        )


class TestStructLayout:

    def test_actor_is_six_bytes(self, built_compiler):
        actor = built_compiler.words["/actor"]
        assert actor.value == 6, (
            "/actor should be 2 + 2 + 1 + 1 = 6 bytes"
        )

    def test_boss_is_eight_bytes(self, built_compiler):
        boss = built_compiler.words["/boss"]
        assert boss.value == 8, (
            "/boss inherits /actor (6 bytes) and adds .rage (2 bytes) = 8 bytes"
        )

    @pytest.mark.parametrize("field,expected_offset", [
        (".x",  0),
        (".y",  2),
        (".hp", 4),
        (".mp", 5),
        (".rage", 6),
    ])
    def test_field_offset(self, built_compiler, field, expected_offset):
        assert built_compiler.words[field].value == expected_offset, (
            f"{field} should have offset {expected_offset} so accessors land "
            f"on the right byte"
        )


class TestStaticFusionFiresOnRecordPlusField:
    """setup-actors performs many `<value> <record> .<field> >!` writes —
    each of those is the textbook static-instance pattern. Every such
    operation must collapse to one NativeStore / NativeFetch cell."""

    def test_setup_actors_uses_only_native_stores(self, built_compiler):
        body = built_compiler.words["setup-actors"].body
        stores = [c for c in body if isinstance(c, NativeStore)]
        assert len(stores) == 13, (
            f"setup-actors writes 13 fields (4 hero + 4 goblin + 5 troll); "
            f"all 13 should fuse to NativeStore cells, got {len(stores)}"
        )

    def test_setup_actors_has_no_threaded_plus_or_store(self, built_compiler):
        from zt.compile.ir import PrimRef
        body = built_compiler.words["setup-actors"].body
        threaded = [c for c in body
                    if isinstance(c, PrimRef) and c.name in ("+", "!", "c!")]
        assert threaded == [], (
            f"setup-actors should not have threaded `+`/`!`/`c!` calls — they "
            f"should all have fused away. Found: {threaded!r}"
        )

    def test_each_field_fused_with_correct_target(self, built_compiler):
        body = built_compiler.words["setup-actors"].body
        targets = {cell.target for cell in body if isinstance(cell, NativeStore)}
        assert targets == {"hero", "goblin", "troll"}, (
            f"every fused store should carry the right record target; "
            f"got {targets!r}"
        )

    def test_byte_widths_distinguished_from_cell_widths(self, built_compiler):
        body = built_compiler.words["setup-actors"].body
        cell_w = sum(1 for c in body
                     if isinstance(c, NativeStore) and c.width == "cell")
        byte_w = sum(1 for c in body
                     if isinstance(c, NativeStore) and c.width == "byte")
        assert cell_w == 7, (
            "7 cell-width writes: 2 each for hero/goblin (.x, .y), 2 for "
            "troll (.x, .y), and 1 for troll (.rage)"
        )
        assert byte_w == 6, (
            "6 byte-width writes: 2 each for hero/goblin/troll (.hp, .mp)"
        )


class TestDynamicFusionFiresInAccessorColons:
    """Generic accessors like actor-x take a runtime instance. Their bodies
    should each collapse to one NativeOffsetFetch / NativeOffsetStore plus
    EXIT — nothing else."""

    @pytest.mark.parametrize("name,expected_class,expected_width,expected_offset", [
        ("actor-x",     NativeOffsetFetch, "cell", 0),
        ("actor-y",     NativeOffsetFetch, "cell", 2),
        ("actor-hp",    NativeOffsetFetch, "byte", 4),
        ("actor-mp",    NativeOffsetFetch, "byte", 5),
        ("boss-rage",   NativeOffsetFetch, "cell", 6),
        ("set-actor-x",  NativeOffsetStore, "cell", 0),
        ("set-actor-y",  NativeOffsetStore, "cell", 2),
        ("set-actor-hp", NativeOffsetStore, "byte", 4),
        ("set-boss-rage", NativeOffsetStore, "cell", 6),
    ])
    def test_accessor_compiles_to_one_offset_cell(
        self, built_compiler, name, expected_class, expected_width, expected_offset,
    ):
        body = built_compiler.words[name].body
        offset_cells = [c for c in body if isinstance(c, expected_class)]
        assert len(offset_cells) == 1, (
            f"{name!r} should have exactly one {expected_class.__name__} cell "
            f"after fusion, got body {body!r}"
        )
        assert offset_cells[0].offset == expected_offset, (
            f"{name!r} should target offset {expected_offset}"
        )
        assert offset_cells[0].width == expected_width, (
            f"{name!r} should use width {expected_width!r}"
        )


class TestRuntimeBehaviour:
    """One round of combat with the simulator — the final HP values must
    match what the README and source comments claim."""

    @pytest.fixture(scope="class")
    def stack_after_main(self, built_compiler):
        c = built_compiler
        m = Z80()
        m.load(c.origin, c.asm.resolve())
        m.pc = c.words["_start"].address
        m.run()
        assert m.halted, "structs example should halt cleanly"
        return _read_data_stack(m, c.data_stack_top, False)

    def test_three_hp_values_left_on_stack(self, stack_after_main):
        assert len(stack_after_main) == 3, (
            f"main should push troll-hp, goblin-hp, hero-hp before halt; "
            f"got {stack_after_main!r}"
        )

    def test_hero_takes_40_damage(self, stack_after_main):
        hero_hp = stack_after_main[2]
        assert hero_hp == 50, (
            f"hero starts at 100 hp, takes 10 + 30 = 40 damage; should end at "
            f"50 hp, got {hero_hp}"
        )

    def test_goblin_takes_25_damage(self, stack_after_main):
        goblin_hp = stack_after_main[1]
        assert goblin_hp == 0, (
            f"goblin starts at 30 hp, takes 25 damage; should end at 0 hp due to several rounds, "
            f"got {goblin_hp}"
        )

    def test_troll_is_untouched(self, stack_after_main):
        troll_hp = stack_after_main[0]
        assert troll_hp == 80, (
            f"troll is not damaged this round; should still be at 80 hp, "
            f"got {troll_hp}"
        )


class TestImageSizeIsPlausible:

    def test_image_fits_in_memory(self, built_compiler):
        size = len(built_compiler.asm.code)
        assert size < 8 * 1024, (
            f"the structs example should be small (< 8KB); "
            f"current size {size} bytes"
        )
