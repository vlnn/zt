from __future__ import annotations

import pytest


@pytest.fixture
def fresh_registry(monkeypatch):
    from zt.assemble import primitive_registry
    monkeypatch.setattr(primitive_registry, "PRIMITIVES", [])
    return primitive_registry


class TestPrimitiveDecorator:

    def test_returns_function_unchanged(self, fresh_registry):
        def fn(a):
            return a
        decorated = fresh_registry.primitive(fn)
        assert decorated is fn, "primitive decorator should return the original function unchanged"

    def test_appends_to_registry(self, fresh_registry):
        def fn(a):
            return a
        fresh_registry.primitive(fn)
        assert fn in fresh_registry.PRIMITIVES, "decorated function should appear in PRIMITIVES"

    def test_preserves_definition_order(self, fresh_registry):
        @fresh_registry.primitive
        def first(a): pass

        @fresh_registry.primitive
        def second(a): pass

        @fresh_registry.primitive
        def third(a): pass

        assert fresh_registry.PRIMITIVES == [first, second, third], (
            "PRIMITIVES should reflect decoration order"
        )


class TestLiveRegistry:

    def test_main_primitives_register_before_sprite_primitives(self):
        from zt.assemble.primitives import PRIMITIVES, create_next, create_execute
        from zt.assemble.sprite_primitives import create_lock_sprites

        idx_next = PRIMITIVES.index(create_next)
        idx_execute = PRIMITIVES.index(create_execute)
        idx_lock = PRIMITIVES.index(create_lock_sprites)

        assert idx_next < idx_execute < idx_lock, (
            "main primitives should register before sprite primitives"
        )

    @pytest.mark.parametrize("creator_name", [
        "create_next", "create_docol", "create_dup", "create_drop",
        "create_plus", "create_fetch", "create_store", "create_emit",
        "create_lock_sprites", "create_blit8", "create_sprite_scratch",
    ])
    def test_known_primitive_is_registered(self, creator_name):
        from zt.assemble import primitives, sprite_primitives
        from zt.assemble.primitive_registry import PRIMITIVES

        creator = getattr(primitives, creator_name, None) \
            or getattr(sprite_primitives, creator_name)

        assert creator in PRIMITIVES, (
            f"{creator_name} should be registered in PRIMITIVES"
        )

    def test_no_duplicate_registrations(self):
        from zt.assemble.primitives import PRIMITIVES
        assert len(PRIMITIVES) == len(set(PRIMITIVES)), (
            "PRIMITIVES should not contain duplicate creators"
        )
