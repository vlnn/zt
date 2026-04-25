from __future__ import annotations

from typing import Callable

_IMMEDIATE_ATTR = "_zt_immediate_name"
_DIRECTIVE_ATTR = "_zt_directive_name"


def immediate(name: str) -> Callable:
    return _tag_decorator(_IMMEDIATE_ATTR, name)


def directive(name: str) -> Callable:
    return _tag_decorator(_DIRECTIVE_ATTR, name)


def collected_immediates(cls: type) -> list[tuple[str, Callable]]:
    return _collect(cls, _IMMEDIATE_ATTR)


def collected_directives(cls: type) -> list[tuple[str, Callable]]:
    return _collect(cls, _DIRECTIVE_ATTR)


def _tag_decorator(attr: str, name: str) -> Callable:
    def decorator(fn: Callable) -> Callable:
        existing = getattr(fn, attr, None)
        if existing is not None:
            raise ValueError(
                f"{fn.__qualname__} is already registered with name {existing!r}"
            )
        setattr(fn, attr, name)
        return fn
    return decorator


def _collect(cls: type, attr: str) -> list[tuple[str, Callable]]:
    seen: dict[str, str] = {}
    entries: list[tuple[str, Callable]] = []
    for klass in reversed(cls.__mro__):
        for fn_name, value in vars(klass).items():
            registered_name = getattr(value, attr, None)
            if registered_name is None:
                continue
            if registered_name in seen and klass is cls:
                raise ValueError(
                    f"{registered_name!r} already registered for {seen[registered_name]}"
                )
            seen[registered_name] = getattr(value, "__qualname__", fn_name)
            entries = [(n, v) for n, v in entries if n != registered_name]
            entries.append((registered_name, value))
    return entries
