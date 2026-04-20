"""
Builds `examples/mined-out/main.fs` end-to-end and asserts the multi-file
mined-out port compiles cleanly and exposes the words each module is
responsible for.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zt.compile.compiler import Compiler


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "mined-out"
MAIN = EXAMPLE_DIR / "main.fs"


@pytest.fixture(scope="module")
def built_compiler() -> Compiler:
    c = Compiler()
    c.include_stdlib()
    c.compile_source(MAIN.read_text(), source=str(MAIN))
    c.compile_main_call()
    c.build()
    return c


class TestMinedOutLayout:

    @pytest.mark.parametrize("relpath", [
        "main.fs",
        "app/mined.fs",
        "app/state.fs",
        "app/sounds.fs",
        "app/board.fs",
        "app/cheat.fs",
        "app/actors.fs",
        "app/hud.fs",
        "app/menu.fs",
        "app/title.fs",
        "app/game.fs",
    ])
    def test_example_files_exist(self, relpath):
        assert (EXAMPLE_DIR / relpath).is_file(), (
            f"mined-out should ship {relpath} under the multi-file layout"
        )


class TestMinedOutCompiles:

    def test_compiles_cleanly(self, built_compiler):
        assert "main" in built_compiler.words, (
            "mined-out example should produce a 'main' word"
        )


class TestMinedOutWordsByModule:

    @pytest.mark.parametrize("word", [
        "score", "level-no", "ti", "max-level-reached", "initial-bonus-pending",
        "level-paper", "level-border", "level-mines", "level-bonus",
        "level-paper@", "level-border@", "level-mines@", "level-bonus@",
        "has-damsels?", "has-spreader?", "has-bug?", "has-map-blow?", "has-bill?",
        "has-closed-gap?", "has-wind?",
        "map-blow-threshold", "map-blow-due?", "wind-period", "reset-ti",
        "advance-level", "bump-max-level", "apply-level-colors",
        "contrast-ink",
    ])
    def test_state_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/state.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "click", "proximity", "explosion", "fanfare", "rescue-chirp", "bug-hiss",
    ])
    def test_sounds_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/sounds.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "board-init", "tile!", "tile@",
        "empty?", "fence?", "mine?", "damsel?",
        "erase-at", "fence-at", "mine-at", "player-at",
        "damsel-at", "spreader-at", "bug-at", "bill-at", "wind-at",
        "trail-at", "trail-attr", "wind-attr",
        "gap?", "fence-row", "build-fences", "build-side-walls", "side-wall-row",
        "left-wall-col", "right-wall-col", "banner-row",
        "place-fence-cell", "erase-cell",
        "try-place-mine", "scatter-mines",
        "show-all-mines", "hide-all-mines",
        "close-top-gap", "open-top-gap", "gap-open?",
    ])
    def test_board_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/board.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "player-xy", "player-xy!", "player-reset", "snapshot-pos", "moved?",
        "apply-input", "try-move",
        "caps?", "plain-key?", "shifted-key?",
        "move-left?", "move-right?", "move-up?", "move-down?",
        "read-dx", "read-dy",
        "pick-damsels", "rescue-damsel", "maybe-rescue",
        "maybe-spawn-spreader", "spreader-step",
        "spreader-row-jitter", "spreader-trail-row",
        "bug-step", "bug-reset", "player-hit-bug?",
        "wind-reset", "wind-step", "wind-due?", "player-hit-by-wind?",
        "wind-col", "wind-row", "wind-idx", "wind-active",
        "bill-col", "bill-row", "pick-bill", "place-bill", "bill?",
        "draw-chamber",
    ])
    def test_actors_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/actors.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "adj-count", "draw-hud", "update-hud",
        "trail-setup", "record-step", "action-replay",
        "show-initial-bonus", "show-level-intro", "clear-banner-row",
        "slow-held?", "end-held?", "replay-frames",
    ])
    def test_hud_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/hud.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "cheat-reset", "cheat-observe", "cheat-fired?",
        "cheat-watching?", "cheat-locked?", "cheat-target",
    ])
    def test_cheat_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/cheat.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "valid-level-key?", "key->level", "apply-level-select",
        "read-valid-level", "select-level", "intro-key?",
        "wait-real-key",
    ])
    def test_menu_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/menu.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "press-any-key",
        "quicksilva-banner", "title-card", "instructions",
        "show-intro",
    ])
    def test_title_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/title.fs should define '{word}'"
        )

    @pytest.mark.parametrize("word", [
        "init-game", "init-level", "end-of-level",
        "tick-world", "after-player-move",
        "step-once", "play-loop",
        "won?", "die", "win",
        "reward-level", "reward-bill", "speed-bonus",
        "check-hiscore", "record-hiscore",
        "continue-or-restart", "reset-for-new-game",
        "should-select-level?",
        "blow-map-away", "bill-banner", "bill-rescued",
        "maybe-open-gap",
    ])
    def test_game_module_words(self, built_compiler, word):
        assert word in built_compiler.words, (
            f"app/game.fs should define '{word}'"
        )


class TestMinedOutRequireDedup:

    def test_stdlib_grid_registered_once(self, built_compiler):
        grid_paths = [p for p in built_compiler.include_resolver.seen_paths()
                      if p.name == "grid.fs"]
        assert len(grid_paths) == 1, (
            "grid.fs is pulled in by board.fs and via stdlib; it should "
            "appear exactly once in the resolved include list"
        )

    def test_stdlib_trail_registered_once(self, built_compiler):
        trail_paths = [p for p in built_compiler.include_resolver.seen_paths()
                       if p.name == "trail.fs"]
        assert len(trail_paths) == 1, (
            "trail.fs is pulled in by actors.fs and hud.fs; it should "
            "appear exactly once in the resolved include list"
        )
