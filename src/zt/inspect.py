from dataclasses import dataclass, field
from typing import Any

from zt.ir import Branch, ColonRef, Label, Literal, PrimRef, StringRef, cells_from_json


DOCOL_CALL_SIZE = 3


def decompile(fsym: dict[str, Any], image: bytes | None = None) -> str:
    words_by_addr = _words_by_address(fsym["words"])
    origin = fsym.get("origin", 0x8000)
    reader = _ImageReader(image, origin) if image else None
    string_labels = fsym.get("string_labels")
    blocks = [_decompile_word(name, info, words_by_addr, reader, string_labels)
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


def _decompile_word(name: str, info: dict, by_addr: dict[int, str],
                    reader: "_ImageReader | None",
                    string_labels: dict[str, int] | None) -> str:
    body_start = info["address"] + DOCOL_CALL_SIZE
    if "cells" in info:
        instrs = _parse_cells(cells_from_json(info["cells"]))
    else:
        instrs = _parse_body(info.get("body", []), by_addr, body_start)
    tokens = _render(instrs, reader, string_labels)
    header = f": {name}  ( ${info['address']:04X} )"
    return f"{header}\n    {' '.join(tokens)}"


@dataclass
class _Instr:
    kind: str
    idx: int
    width: int = 1
    value: int = 0
    target: int = 0
    name: str = ""


def _parse_cells(cells: list) -> list[_Instr]:
    label_positions = _label_positions(cells)
    instrs: list[_Instr] = []
    for idx, cell in enumerate(cells):
        instrs.append(_instr_from_cell(cell, idx, label_positions))
    return instrs


def _label_positions(cells: list) -> dict[int, int]:
    return {cell.id: idx for idx, cell in enumerate(cells)
            if isinstance(cell, Label)}


def _instr_from_cell(cell: Any, idx: int, label_positions: dict[int, int]) -> _Instr:
    if isinstance(cell, Literal):
        return _Instr(kind="lit", idx=idx, value=cell.value)
    if isinstance(cell, Branch):
        return _Instr(
            kind=_branch_kind(cell.kind), idx=idx,
            target=label_positions[cell.target.id],
        )
    if isinstance(cell, Label):
        return _Instr(kind="label", idx=idx)
    if isinstance(cell, StringRef):
        return _Instr(kind="str", idx=idx, name=cell.label)
    if isinstance(cell, (PrimRef, ColonRef)):
        return _instr_from_word_ref(cell, idx)
    raise TypeError(f"unknown cell type in body: {type(cell).__name__}")


def _branch_kind(ir_kind: str) -> str:
    if ir_kind == "(loop)":
        return "loop"
    if ir_kind == "(+loop)":
        return "+loop"
    return ir_kind


def _instr_from_word_ref(cell: Any, idx: int) -> _Instr:
    name = cell.name
    if name == "(do)":
        return _Instr(kind="do", idx=idx)
    if name == "unloop":
        return _Instr(kind="unloop", idx=idx)
    if name == "exit":
        return _Instr(kind="exit", idx=idx)
    return _Instr(kind="call", idx=idx, name=name)


def _parse_body(body: list[int], by_addr: dict[int, str],
                body_start_addr: int) -> list[_Instr]:
    instrs: list[_Instr] = []
    i = 0
    while i < len(body):
        cell = body[i]
        name = by_addr.get(cell)
        instr = _parse_one(body, i, name, body_start_addr)
        instrs.append(instr)
        i += instr.width
    return instrs


def _parse_one(body: list[int], i: int, name: str | None,
               body_start_addr: int) -> _Instr:
    if name == "lit" and i + 1 < len(body):
        return _Instr(kind="lit", idx=i, width=2, value=body[i + 1])
    if name in ("branch", "0branch") and i + 1 < len(body):
        return _Instr(kind=name, idx=i, width=2,
                      target=_addr_to_idx(body[i + 1], body_start_addr))
    if name in ("(loop)", "(+loop)") and i + 1 < len(body):
        kind = "loop" if name == "(loop)" else "+loop"
        return _Instr(kind=kind, idx=i, width=2,
                      target=_addr_to_idx(body[i + 1], body_start_addr))
    if name == "(do)":
        return _Instr(kind="do", idx=i)
    if name == "unloop":
        return _Instr(kind="unloop", idx=i)
    if name == "exit":
        return _Instr(kind="exit", idx=i)
    if name is not None:
        return _Instr(kind="call", idx=i, name=name)
    return _Instr(kind="raw", idx=i, value=body[i])


def _addr_to_idx(address: int, body_start_addr: int) -> int:
    return (address - body_start_addr) // 2


def _begin_targets(instrs: list[_Instr]) -> set[int]:
    return {inst.target for inst in instrs
            if inst.kind in ("branch", "0branch") and inst.target < inst.idx}


def _render(instrs: list[_Instr], reader: "_ImageReader | None",
            string_labels: dict[str, int] | None) -> list[str]:
    begins = _begin_targets(instrs)
    stack: list[dict] = []
    tokens: list[str] = []
    i = 0
    while i < len(instrs):
        inst = instrs[i]
        _close_conditionals(stack, tokens, inst.idx)
        _open_begin_if_needed(stack, tokens, begins, inst.idx)
        i = _emit(instrs, i, stack, tokens, reader, string_labels)
    _close_conditionals(stack, tokens, float("inf"))
    return tokens


def _close_conditionals(stack: list[dict], tokens: list[str], idx: float) -> None:
    while stack and stack[-1]["kind"] in ("if", "else") \
            and stack[-1]["close_at"] <= idx:
        stack.pop()
        tokens.append("then")


def _open_begin_if_needed(stack: list[dict], tokens: list[str],
                          begins: set[int], idx: int) -> None:
    if idx not in begins:
        return
    if any(s["kind"] == "begin" and s.get("begin_idx") == idx for s in stack):
        return
    stack.append({"kind": "begin", "begin_idx": idx})
    tokens.append("begin")


def _emit(instrs: list[_Instr], i: int, stack: list[dict],
          tokens: list[str], reader: "_ImageReader | None",
          string_labels: dict[str, int] | None) -> int:
    inst = instrs[i]
    if inst.kind == "label":
        return i + 1
    if inst.kind == "str":
        tokens.append(f"<{inst.name}>")
        return i + 1
    if inst.kind == "lit":
        return _emit_lit(instrs, i, tokens, reader)
    if inst.kind == "branch":
        return _emit_branch(inst, instrs, i, stack, tokens)
    if inst.kind == "0branch":
        return _emit_zbranch(inst, stack, tokens) or i + 1
    if inst.kind == "do":
        stack.append({"kind": "do"})
        tokens.append("do")
        return i + 1
    if inst.kind in ("loop", "+loop"):
        if stack and stack[-1]["kind"] == "do":
            stack.pop()
        tokens.append(inst.kind)
        return i + 1
    if inst.kind == "unloop":
        return _emit_unloop(instrs, i, tokens)
    if inst.kind == "exit":
        tokens.append(";" if i == len(instrs) - 1 else "exit")
        return i + 1
    if inst.kind == "call":
        consumed = _try_dot_quote_cells(instrs, i, tokens, reader, string_labels)
        if consumed:
            return i + consumed
        tokens.append(inst.name)
        return i + 1
    tokens.append(f"${inst.value:04X}")
    return i + 1


def _try_dot_quote_cells(instrs: list[_Instr], i: int, tokens: list[str],
                         reader: "_ImageReader | None",
                         string_labels: dict[str, int] | None) -> int:
    if reader is None or string_labels is None:
        return 0
    if i + 3 >= len(instrs):
        return 0
    a, b, c, d = instrs[i], instrs[i + 1], instrs[i + 2], instrs[i + 3]
    if a.kind != "call" or a.name != "lit":
        return 0
    if b.kind != "str":
        return 0
    if c.kind != "lit":
        return 0
    if d.kind != "call" or d.name != "type":
        return 0
    addr = string_labels.get(b.name)
    if addr is None:
        return 0
    data = reader.read(addr, c.value)
    if data is None:
        return 0
    tokens.append(f'." {data.decode("latin-1")}"')
    return 4


def _emit_lit(instrs: list[_Instr], i: int, tokens: list[str],
              reader: "_ImageReader | None") -> int:
    consumed = _try_dot_quote(instrs, i, tokens, reader)
    if consumed:
        return i + consumed
    tokens.append(str(_signed(instrs[i].value)))
    return i + 1


def _try_dot_quote(instrs: list[_Instr], i: int, tokens: list[str],
                   reader: "_ImageReader | None") -> int:
    if reader is None:
        return 0
    if i + 2 >= len(instrs):
        return 0
    a, b, c = instrs[i], instrs[i + 1], instrs[i + 2]
    if a.kind != "lit" or b.kind != "lit":
        return 0
    if c.kind != "call" or c.name != "type":
        return 0
    data = reader.read(a.value, b.value)
    if data is None:
        return 0
    tokens.append(f'." {data.decode("latin-1")}"')
    return 3


def _emit_branch(inst: _Instr, instrs: list[_Instr], i: int,
                 stack: list[dict], tokens: list[str]) -> int:
    if inst.target < inst.idx:
        return _emit_backward_branch(inst, stack, tokens, i)
    return _emit_forward_branch(inst, instrs, i, stack, tokens)


def _emit_backward_branch(inst: _Instr, stack: list[dict],
                          tokens: list[str], i: int) -> int:
    if stack and stack[-1]["kind"] == "while":
        stack.pop()
        if stack and stack[-1]["kind"] == "begin":
            stack.pop()
        tokens.append("repeat")
        return i + 1
    if stack and stack[-1]["kind"] == "begin" \
            and stack[-1]["begin_idx"] == inst.target:
        stack.pop()
        tokens.append("again")
        return i + 1
    tokens.append(f"branch ${inst.target:04X}")
    return i + 1


def _emit_forward_branch(inst: _Instr, instrs: list[_Instr], i: int,
                         stack: list[dict], tokens: list[str]) -> int:
    if i > 0 and instrs[i - 1].kind == "unloop":
        return i + 1
    if stack and stack[-1]["kind"] == "if":
        stack.pop()
        stack.append({"kind": "else", "close_at": inst.target})
        tokens.append("else")
        return i + 1
    tokens.append(f"branch ${inst.target:04X}")
    return i + 1


def _emit_zbranch(inst: _Instr, stack: list[dict],
                  tokens: list[str]) -> int | None:
    if inst.target < inst.idx:
        if stack and stack[-1]["kind"] == "begin":
            stack.pop()
            tokens.append("until")
            return None
        tokens.append(f"0branch ${inst.target:04X}")
        return None
    if stack and stack[-1]["kind"] == "begin":
        stack.append({"kind": "while"})
        tokens.append("while")
        return None
    stack.append({"kind": "if", "close_at": inst.target})
    tokens.append("if")
    return None


def _emit_unloop(instrs: list[_Instr], i: int, tokens: list[str]) -> int:
    nxt = instrs[i + 1] if i + 1 < len(instrs) else None
    if nxt and nxt.kind == "branch" and nxt.target > nxt.idx:
        tokens.append("leave")
        return i + 2
    tokens.append("unloop")
    return i + 1


def _signed(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value


class _ImageReader:
    def __init__(self, image: bytes, origin: int) -> None:
        self.image = image
        self.origin = origin

    def read(self, addr: int, length: int) -> bytes | None:
        offset = addr - self.origin
        if offset < 0 or offset + length > len(self.image):
            return None
        return bytes(self.image[offset:offset + length])
