from typing import Any


INLINE_VALUE_WORDS = frozenset({"lit"})
INLINE_TARGET_WORDS = frozenset({"branch", "0branch"})


def decompile(fsym: dict[str, Any]) -> str:
    words_by_addr = _words_by_address(fsym["words"])
    blocks = [_decompile_word(name, info, words_by_addr)
              for name, info in fsym["words"].items()
              if info["kind"] == "colon"]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _words_by_address(words: dict[str, dict]) -> dict[int, str]:
    result: dict[int, str] = {}
    for name, info in words.items():
        addr = info["address"]
        current = result.get(addr)
        if current is None or _prefer(name, current):
            result[addr] = name
    return result


def _prefer(candidate: str, current: str) -> bool:
    if len(candidate) != len(current):
        return len(candidate) < len(current)
    return candidate < current


def _decompile_word(name: str, info: dict, by_addr: dict[int, str]) -> str:
    header = f": {name}  ( ${info['address']:04X} )"
    tokens = _body_tokens(info.get("body", []), by_addr)
    return f"{header}\n    {' '.join(tokens)}"


def _body_tokens(body: list[int], by_addr: dict[int, str]) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(body):
        cell = body[i]
        name = by_addr.get(cell)
        consumed = _try_consume(name, body, i, tokens)
        i += consumed
    return tokens


def _try_consume(name: str | None, body: list[int], i: int,
                 tokens: list[str]) -> int:
    if name in INLINE_VALUE_WORDS and i + 1 < len(body):
        tokens.append(str(_signed(body[i + 1])))
        return 2
    if name in INLINE_TARGET_WORDS and i + 1 < len(body):
        tokens.append(f"{name} ${body[i + 1]:04X}")
        return 2
    if name == "exit" and i == len(body) - 1:
        tokens.append(";")
        return 1
    tokens.append(name if name is not None else f"${body[i]:04X}")
    return 1


def _signed(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value
