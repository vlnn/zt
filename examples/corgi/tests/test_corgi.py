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
        "bone", "stick", "ball", "carried",
        "exits-table", "item-room", "here-room",
        "exit-of", "blocked?", "carrying?", "here?", "have-stick?",
        "place-items", "init-exits", "connect",
    ])
    def test_world_words_defined(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"world.fs should define '{word}'"
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
        "kitchen", "hallway", "garden", "road", "well",
        "bone", "stick", "ball", "carried",
        "msg-welcome", "msg-no-exit", "msg-took",
    ])
    def test_named_constants_have_constant_kind(self, built_compiler, name):
        assert built_compiler.words[name].kind == "constant", (
            f"{name} should be a constant"
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
