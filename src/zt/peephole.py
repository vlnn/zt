from __future__ import annotations

from dataclasses import dataclass
from typing import Union

PatternElement = Union[str, int]


@dataclass(frozen=True)
class PeepholeRule:
    pattern: tuple[PatternElement, ...]
    replacement: str


DEFAULT_RULES: tuple[PeepholeRule, ...] = (
    PeepholeRule((0,),              "zero"),
    PeepholeRule((1,),              "one"),
    PeepholeRule((1, "+"),          "1+"),
    PeepholeRule((1, "-"),          "1-"),
    PeepholeRule((2, "*"),          "2*"),
    PeepholeRule(("dup", "@"),      "dup@"),
    PeepholeRule(("swap", "drop"),  "nip"),
    PeepholeRule(("drop", "drop"),  "2drop"),
    PeepholeRule(("over", "over"),  "2dup"),
)


def rules_by_specificity(
    rules: tuple[PeepholeRule, ...],
) -> tuple[PeepholeRule, ...]:
    return tuple(sorted(rules, key=lambda r: -len(r.pattern)))


def max_pattern_length(rules: tuple[PeepholeRule, ...]) -> int:
    return max((len(r.pattern) for r in rules), default=0)


def find_match(
    elements: list[PatternElement | None],
    rules: tuple[PeepholeRule, ...],
) -> PeepholeRule | None:
    for rule in rules_by_specificity(rules):
        n = len(rule.pattern)
        if n > len(elements):
            continue
        window = elements[:n]
        if any(e is None for e in window):
            continue
        if tuple(window) == rule.pattern:
            return rule
    return None
