"""
Tests for redefining a name that earlier code still refers to. Each definition keeps its
own identity, so IR-driven builds (tree-shaken, native) bind old references to the old
definition exactly as the eager build does.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from native_harness import compile_program
from zt.compile.compiler import Compiler, Word
from zt.compile.dictionary import Dictionary
from zt.sim import Z80, _read_data_stack

BUILDS = {
    "eager": lambda c: (c.build(), c.words["_start"].address),
    "tree-shaken": lambda c: c.build_tree_shaken(),
    "native": lambda c: c.build_native(),
}

PROGRAMS = {
    "variable-shadowed-by-create": (
        "variable buf  : set-old 111 buf ! ;  : get-old buf @ ; "
        "create buf 222 , "
        ": main set-old get-old buf @ halt ;",
        (111, 222),
    ),
    "colon-shadowed-by-colon": (
        ": f 1 ; : g f ; : f 2 ; : main g f halt ;",
        (1, 2),
    ),
    "constant-shadowed-by-constant": (
        "5 constant k : old-k k ; 9 constant k : main old-k k halt ;",
        (5, 9),
    ),
    "primitive-shadowed-by-colon": (
        ": twice dup + ; : dup 99 ; : main 4 twice dup halt ;",
        (8, 99),
    ),
    "primitive-shadowed-by-variable": (
        ": twice dup + ; variable dup : main 4 twice 7 dup ! dup @ halt ;",
        (8, 7),
    ),
    "word-named-like-a-peephole-target": (
        ": one 1 ; : zero 0 ; : main one zero halt ;",
        (1, 0),
    ),
    "tick-of-shadowed-word": (
        ": f 1 ; create table ' f , : f 2 ; : main table @ execute f halt ;",
        (1, 2),
    ),
}


def _stack(source: str, build: str) -> tuple[int, ...]:
    compiler = compile_program(source)
    image, start = BUILDS[build](compiler)
    machine = Z80()
    machine.load(compiler.origin, image)
    machine.pc = start
    machine.run(max_ticks=200_000)
    assert machine.halted, f"{build} build should reach HALT"
    return tuple(_read_data_stack(machine, compiler.data_stack_top, False))


def _word(name: str, kind: str = "colon", **fields) -> Word:
    return Word(name=name, address=0x8000, kind=kind, **fields)


class TestDictionaryDefine:

    def test_first_definition_keeps_its_name(self):
        words = Dictionary()
        words.define(_word("f"))
        assert words["f"].name == "f", "an unshadowed word should keep its source name"

    def test_second_definition_gets_a_distinct_identity(self):
        words = Dictionary()
        words.define(_word("f"))
        words.define(_word("f"))
        assert words["f"].name != "f", \
            "a redefinition should get an identity distinct from the word it shadows"

    def test_source_lookup_sees_the_latest_definition(self):
        words = Dictionary()
        old, new = _word("f"), _word("f")
        words.define(old)
        words.define(new)
        assert words["f"] is new and words.get("f") is new, \
            "looking a name up should return its latest definition"

    def test_identity_lookup_still_reaches_the_shadowed_definition(self):
        words = Dictionary()
        old = _word("f")
        words.define(old)
        words.define(_word("f"))
        assert words.definition("f") is old, \
            "the shadowed definition should stay reachable by its identity"

    def test_both_definitions_are_iterated(self):
        words = Dictionary()
        words.define(_word("f"))
        words.define(_word("f"))
        assert len(list(words.values())) == 2, \
            "iteration should cover the shadowed definition as well as the new one"

    def test_third_definition_does_not_collide_with_second(self):
        words = Dictionary()
        for _ in range(3):
            words.define(_word("f"))
        assert len({w.name for w in words.values()}) == 3, \
            "every redefinition should get its own identity"

    def test_compile_time_word_is_replaced_not_shadowed(self):
        words = Dictionary()
        words.define(_word("field", kind="constant", immediate=True, compile_action=print))
        words.define(_word("field"))
        assert len(list(words.values())) == 1, \
            "an immediate word is never referenced by IR and should simply be replaced"

    def test_deleting_the_latest_definition_reveals_the_old_one(self):
        words = Dictionary()
        old = _word("f")
        words.define(old)
        words.define(_word("f"))
        del words[words["f"].name]
        assert words["f"] is old, \
            "removing the shadowing definition should make the name resolve to the old one"

    def test_unknown_identity_raises(self):
        with pytest.raises(KeyError):
            Dictionary().definition("ghost")


class TestShadowingSemantics:

    @pytest.mark.parametrize("build", BUILDS)
    @pytest.mark.parametrize("name", PROGRAMS)
    def test_old_references_keep_their_old_target(self, name, build):
        source, expected = PROGRAMS[name]
        assert _stack(source, build) == expected, \
            f"{build} build of {name!r} should bind each reference to the definition " \
            f"that was current when it was compiled"


class TestRedefinitionWarning:

    def test_redefining_a_colon_still_warns(self):
        c = Compiler()
        c.compile_source(": f 1 ;\n: f 2 ;")
        assert any("redefining 'f'" in w for w in c.warnings), \
            "redefining a colon word should still produce a warning naming it"
