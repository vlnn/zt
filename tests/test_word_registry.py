from __future__ import annotations

import pytest

from zt.word_registry import (
    collected_directives,
    collected_immediates,
    directive,
    immediate,
)


class TestImmediateDecorator:

    def test_immediate_marks_method(self):
        class C:
            @immediate("foo")
            def handle_foo(self, compiler, tok): pass
        entries = collected_immediates(C)
        names = [name for name, _ in entries]
        assert "foo" in names, "immediate decorator should register its name"

    def test_immediate_preserves_method(self):
        class C:
            @immediate("foo")
            def handle_foo(self, compiler, tok): return 42
        c = C()
        assert c.handle_foo(None, None) == 42, (
            "immediate should not break the underlying method's behaviour"
        )

    def test_multiple_immediates_are_all_collected(self):
        class C:
            @immediate("a")
            def h_a(self, compiler, tok): pass
            @immediate("b")
            def h_b(self, compiler, tok): pass
            @immediate("c")
            def h_c(self, compiler, tok): pass
        names = [name for name, _ in collected_immediates(C)]
        assert set(names) == {"a", "b", "c"}, (
            "all @immediate-decorated methods should appear in the registry"
        )

    def test_immediate_handler_resolves_against_instance(self):
        class C:
            @immediate("foo")
            def handle_foo(self, compiler, tok):
                return self.tag

        c = C()
        c.tag = "ok"
        entries = dict(collected_immediates(C))
        bound = entries["foo"].__get__(c, C)
        assert bound(None, None) == "ok", (
            "collected handler should be resolvable to a bound method on an instance"
        )


class TestDirectiveDecorator:

    def test_directive_marks_method(self):
        class C:
            @directive(",")
            def handle_comma(self, compiler, tok): pass
        entries = collected_directives(C)
        names = [name for name, _ in entries]
        assert "," in names, "directive decorator should register its name"

    def test_directive_and_immediate_registries_are_separate(self):
        class C:
            @immediate("foo")
            def h_foo(self, compiler, tok): pass
            @directive("bar")
            def h_bar(self, compiler, tok): pass
        imm_names = [n for n, _ in collected_immediates(C)]
        dir_names = [n for n, _ in collected_directives(C)]
        assert "foo" in imm_names and "foo" not in dir_names, (
            "@immediate entries should go to the immediate registry only"
        )
        assert "bar" in dir_names and "bar" not in imm_names, (
            "@directive entries should go to the directive registry only"
        )


class TestOrderIsDeterministic:

    def test_immediates_keep_definition_order(self):
        class C:
            @immediate("z")
            def h_z(self, compiler, tok): pass
            @immediate("a")
            def h_a(self, compiler, tok): pass
            @immediate("m")
            def h_m(self, compiler, tok): pass
        names = [name for name, _ in collected_immediates(C)]
        assert names == ["z", "a", "m"], (
            "collected_immediates should preserve source-definition order"
        )


class TestInheritance:

    def test_subclass_sees_parent_immediates(self):
        class Parent:
            @immediate("parent_word")
            def h(self, compiler, tok): pass
        class Child(Parent):
            pass
        names = [name for name, _ in collected_immediates(Child)]
        assert "parent_word" in names, (
            "subclass collection should include inherited @immediate handlers"
        )


class TestNameDuplication:

    def test_duplicate_immediate_name_in_same_class_raises_on_collect(self):
        class C:
            @immediate("foo")
            def h1(self, compiler, tok): pass
            @immediate("foo")
            def h2(self, compiler, tok): pass
        with pytest.raises(ValueError, match="already registered"):
            collected_immediates(C)
