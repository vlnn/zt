"""Compilation and behavioural tests for the corgi adventure example."""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler, compile_and_run_with_output


EXAMPLE_DIR = Path(__file__).parent.parent
MAIN = EXAMPLE_DIR / "main.fs"
GAME = EXAMPLE_DIR / "app" / "game.fs"


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestFiles:

    @pytest.mark.parametrize("relpath", [
        "main.fs",
        "app/world.fs",
        "app/game.fs",
    ])
    def test_example_files_exist(self, relpath):
        assert (EXAMPLE_DIR / relpath).is_file(), (
            f"corgi example should ship {relpath}"
        )


class TestCompiles:

    def test_main_defined(self, built_compiler):
        assert "main" in built_compiler.words, (
            "corgi should produce a 'main' word"
        )

    @pytest.mark.parametrize("word", [
        "kitchen", "hallway", "garden", "road", "well",
        "bone", "stick", "ball", "carried", "nowhere",
        "here-room",
        "/room", ".exits", ".description",
        "exit-of", "blocked?", "carrying?", "here?", "have-stick?",
        "room-has?", "in-room?",
        "place-items", "init-exits", "connect", "connect-pair",
        "opposite-dir",
        "item-room@", "item-room!",
        "pick-at",
    ])
    def test_world_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"world.fs should define '{word}'"
        )

    @pytest.mark.parametrize("name", [
        "rooms", "edge-from", "edge-to", "edge-dir",
        "item-loc", "item-homes",
    ])
    def test_world_array_literals_are_variables(self, built_compiler, name):
        assert built_compiler.words[name].kind == "variable", (
            f"{name} should be defined as an array literal (kind variable)"
        )

    @pytest.mark.parametrize("word", [
        "describe-room", "look-here", "list-inventory",
        "do-north", "do-south", "do-east", "do-west", "try-go",
        "do-take", "do-drop", "do-inventory",
        "do-bark", "do-help", "do-look", "do-quit",
        "won?", "celebrate",
        "lower", "read-line", "first-char", "dispatch",
        "render", "final-render", "intro",
        "reset-game", "turn", "run-corgi",
        "show-msg", "last-msg", "last-item",
        "item-printers", "msg-printers",
        "cmd-keys", "cmd-actions",
    ])
    def test_game_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"game.fs should define '{word}'"
        )

    def test_here_room_is_a_variable(self, built_compiler):
        assert built_compiler.words["here-room"].kind == "variable", (
            "here-room should be a variable"
        )

    @pytest.mark.parametrize("name", [
        "bone", "stick", "ball", "carried", "nowhere",
        "dir-n", "dir-s", "dir-e", "dir-w",
        ".exits", ".description",
        "msg-welcome", "msg-no-exit", "msg-took",
    ])
    def test_named_constants_have_constant_kind(self, built_compiler, name):
        assert built_compiler.words[name].kind == "constant", (
            f"{name} should be a constant"
        )

    @pytest.mark.parametrize("name", [
        "kitchen", "hallway", "garden", "road", "well",
    ])
    def test_rooms_are_variables(self, built_compiler, name):
        assert built_compiler.words[name].kind == "variable", (
            f"{name} should be a record (variable kind) holding a /room"
        )

    def test_room_struct_size_is_ten_bytes(self, built_compiler):
        assert built_compiler.words["/room"].kind == "struct", (
            "/room should be defined by STRUCT"
        )
        assert built_compiler.words["/room"].value == 10, (
            "/room should occupy 10 bytes: 8 for .exits + 2 for .description"
        )

    @pytest.mark.parametrize("array,used_for", [
        ("rooms",        "for-each-word over rooms"),
        ("edge-from",    "parallel-array edge installer"),
        ("edge-to",      "parallel-array edge installer"),
        ("edge-dir",     "parallel-array edge installer"),
        ("item-loc",     "id-indexed item state"),
        ("item-homes",   "id-indexed initial placement"),
        ("item-printers", "id-indexed name printers"),
        ("msg-printers", "msg-id-indexed action xts"),
        ("cmd-keys",     "verb-key parallel array"),
        ("cmd-actions",  "verb-action parallel array"),
    ])
    def test_data_driven_arrays_present(self, built_compiler, array, used_for):
        assert array in built_compiler.words, (
            f"{array} should exist as a literal array ({used_for})"
        )


class TestBehaviour:

    def _run(self, snippet: str) -> bytes:
        source = f"""
        require {GAME}
        : main {snippet} halt ;
        """
        _, out = compile_and_run_with_output(source, stdlib=True)
        return out

    def test_describe_room_after_reset_prints_kitchen(self):
        out = self._run("reset-game describe-room")
        assert b"kitchen" in out.lower(), (
            "describe-room after reset-game should print kitchen text"
        )

    def test_look_here_mentions_bone(self):
        out = self._run("reset-game look-here")
        assert b"bone" in out, (
            "looking in the starting room should mention the bone"
        )

    def test_print_help_lists_movement_keys(self):
        out = self._run("print-help")
        for needle in (b"N S E W", b"LOOK", b"TAKE", b"DROP", b"INV", b"BARK", b"HELP", b"QUIT"):
            assert needle in out, f"help should mention {needle!r}"

    @pytest.mark.parametrize("upper,lower_value", [
        (65, 97), (78, 110), (90, 122),
    ])
    def test_lower_on_letters_shifts_by_32(self, upper, lower_value):
        out = self._run(f"{upper} lower u.")
        assert out == f"{lower_value} ".encode(), (
            f"lower of {upper} should produce {lower_value}"
        )

    @pytest.mark.parametrize("c", [48, 57, 63, 33])
    def test_lower_on_non_letter_passes_through(self, c):
        out = self._run(f"{c} lower u.")
        assert out == f"{c} ".encode(), (
            f"lower should leave non-letter {c} unchanged"
        )

    def test_show_msg_after_take_prints_take_text(self):
        out = self._run("reset-game do-take show-msg")
        assert b"take" in out.lower() and b"bone" in out, (
            "show-msg after do-take should announce taking the bone"
        )

    def test_show_msg_after_no_exit_prints_no_exit_text(self):
        out = self._run("reset-game do-east show-msg")
        assert b"way" in out.lower() or b"snoot" in out.lower(), (
            "do-east from kitchen should set the no-exit message"
        )

    @pytest.mark.parametrize("dir_in,dir_out", [
        ("dir-n", "dir-s"),
        ("dir-s", "dir-n"),
        ("dir-e", "dir-w"),
        ("dir-w", "dir-e"),
    ])
    def test_opposite_dir_flips_each_direction(self, dir_in, dir_out):
        out = self._run(f"{dir_in} opposite-dir {dir_out} = .")
        assert out == b"-1 ", (
            f"opposite-dir {dir_in} should equal {dir_out}"
        )

    def test_pick_at_in_kitchen_returns_bone(self):
        out = self._run("reset-game kitchen pick-at u.")
        assert out == b"0 ", (
            "pick-at in kitchen should return bone (id 0)"
        )

    def test_pick_at_in_hallway_returns_minus_one(self):
        out = self._run("reset-game hallway pick-at .")
        assert out == b"-1 ", (
            "pick-at in hallway (no items) should return -1"
        )

    def test_pick_at_carried_after_take_returns_bone(self):
        out = self._run("reset-game do-take carried pick-at u.")
        assert out == b"0 ", (
            "after taking the bone, pick-at carried should return its id"
        )

    @pytest.mark.parametrize("item_word,home_word", [
        ("bone", "kitchen"),
        ("stick", "garden"),
        ("ball", "well"),
    ])
    def test_item_loc_after_place_items(self, item_word, home_word):
        out = self._run(
            f"reset-game {item_word} item-room@ {home_word} = ."
        )
        assert out == b"-1 ", (
            f"after place-items, {item_word} should be in {home_word}"
        )

    def test_dispatch_n_moves_north(self):
        out = self._run("reset-game key-n dispatch here-room @ hallway = .")
        assert out == b"-1 ", (
            "dispatching key-n from kitchen should move to hallway"
        )

    def test_dispatch_t_takes_item(self):
        out = self._run("reset-game key-t dispatch bone item-room@ carried = .")
        assert out == b"-1 ", (
            "dispatching key-t in kitchen should pick up the bone"
        )

    def test_init_exits_is_bidirectional(self):
        out = self._run(
            "reset-game "
            "kitchen dir-n exit-of hallway = "
            "hallway dir-s exit-of kitchen = "
            "and ."
        )
        assert out == b"-1 ", (
            "init-exits should wire kitchen↔hallway in both directions"
        )

    def test_unconnected_direction_remains_blocked(self):
        out = self._run("reset-game kitchen dir-e exit-of blocked? .")
        assert out == b"-1 ", (
            "kitchen has no east exit, so it should remain blocked"
        )
