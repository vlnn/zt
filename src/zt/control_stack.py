"""
Tagged control-flow stack used at compile time by `if/else/then`, `begin/until`, `begin/while/repeat` and `do/loop` to match structured control frames.
"""
from __future__ import annotations

from typing import Any, Iterator


ControlFrame = tuple[str, Any]


class ControlStackError(Exception):
    pass


class ControlStack:

    def __init__(self) -> None:
        self._frames: list[ControlFrame] = []

    def __len__(self) -> int:
        return len(self._frames)

    def __bool__(self) -> bool:
        return bool(self._frames)

    def __iter__(self) -> Iterator[ControlFrame]:
        return iter(self._frames)

    def find_innermost(self, tag: str) -> ControlFrame | None:
        for frame in reversed(self._frames):
            if frame[0] == tag:
                return frame
        return None

    def push(self, tag: str, value: Any) -> None:
        self._frames.append((tag, value))

    def pop(self, expected_tag: str) -> Any:
        tag, value = self._pop_frame(expected_tag)
        if tag != expected_tag:
            raise ControlStackError(
                f"control flow mismatch: expected {expected_tag}, got {tag}"
            )
        return value

    def pop_any(self, expected_tags: list[str]) -> ControlFrame:
        tag, value = self._pop_frame("/".join(expected_tags))
        if tag not in expected_tags:
            raise ControlStackError(
                f"control flow mismatch: expected {'/'.join(expected_tags)}, got {tag}"
            )
        return tag, value

    def peek(self) -> ControlFrame:
        if not self._frames:
            raise ControlStackError("control stack underflow")
        return self._frames[-1]

    def clear(self) -> None:
        self._frames.clear()

    def _pop_frame(self, context: str) -> ControlFrame:
        if not self._frames:
            raise ControlStackError(f"control stack underflow ({context})")
        return self._frames.pop()
