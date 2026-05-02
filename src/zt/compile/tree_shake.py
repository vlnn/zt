"""
Liveness-driven image rebuilding. `build_tree_shaken_image` takes a finished `Compiler` and produces a fresh image containing only the words and strings reachable from `_start`. Supports colons, primitives, strings, constants, variables, `create` definitions, and `[']` (word-address-as-literal via the `WordLiteral` IR cell); `'` (word-address-as-data) and native control flow are not yet supported.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import emit_blob
from zt.compile.ir import cell_size, resolve as ir_resolve
from zt.compile.liveness import Liveness

if TYPE_CHECKING:
    from zt.compile.compiler import Compiler, Word


def build_tree_shaken_image(compiler: Compiler) -> tuple[bytes, int]:
    if compiler.native_control_flow:
        raise NotImplementedError("native_control_flow mode is not yet supported")
    _reject_unsupported_features(compiler)
    liveness = compiler.compute_liveness()
    new_asm = Asm(origin=compiler.origin, inline_next=compiler.inline_next)
    _emit_live_primitives(new_asm, compiler, liveness)
    word_addrs = _allocate_colons(new_asm, compiler, liveness)
    _emit_live_strings(new_asm, compiler, liveness, word_addrs)
    _emit_live_data_words(new_asm, compiler, liveness, word_addrs)
    _patch_colon_bodies(new_asm, compiler, liveness, word_addrs)
    start_addr = _emit_start(new_asm, compiler, word_addrs)
    image = new_asm.resolve()
    _commit_to_compiler(compiler, new_asm, word_addrs, liveness, start_addr)
    return image, start_addr


def _commit_to_compiler(
    compiler: Compiler, new_asm: Asm,
    word_addrs: dict[str, int], liveness: Liveness,
    start_addr: int,
) -> None:
    from zt.compile.compiler import Word
    compiler.asm = new_asm
    dead = [name for name in compiler.words if name not in liveness.words and name != "_start"]
    for name in dead:
        del compiler.words[name]
    for name, word in list(compiler.words.items()):
        if name in word_addrs:
            compiler.words[name] = _word_with_address(word, word_addrs[name])
        elif word.kind == "prim" and name in new_asm.labels:
            compiler.words[name] = _word_with_address(word, new_asm.labels[name])
    compiler.words["_start"] = Word(name="_start", address=start_addr, kind="prim")


def _word_with_address(word: "Word", new_address: int) -> "Word":
    from dataclasses import replace
    return replace(word, address=new_address)


def _reject_unsupported_features(compiler: Compiler) -> None:
    if getattr(compiler, "_uses_word_address_data", False):
        raise NotImplementedError(
            "tick `'` (word-address-as-data) is not yet supported by tree-shaking"
        )
    if compiler.banks():
        raise NotImplementedError(
            "banked code (in-bank/end-bank) is not yet supported by tree-shaking"
        )
    for word in compiler.words.values():
        if word.kind not in {"prim", "colon", "constant", "variable"}:
            raise NotImplementedError(
                f"word kind {word.kind!r} is not yet supported by tree-shaking"
            )


def _emit_live_primitives(new_asm: Asm, compiler: Compiler, liveness: Liveness) -> None:
    for blob in compiler._blob_registry.blobs:
        if not _blob_is_live(blob, liveness):
            continue
        emit_blob(new_asm, blob)
    for blob in getattr(compiler, "_asm_word_blobs", ()):
        if not _blob_is_live(blob, liveness):
            continue
        emit_blob(new_asm, blob)


def _blob_is_live(blob, liveness: Liveness) -> bool:
    return any(name.lower() in liveness.words for name in blob.label_offsets)


def _allocate_colons(
    new_asm: Asm, compiler: Compiler, liveness: Liveness,
) -> dict[str, int]:
    word_addrs = _primitive_addrs(new_asm)
    for word in _live_colons(compiler, liveness):
        word_addrs[word.name] = new_asm.here
        new_asm.call("DOCOL")
        body_size = sum(cell_size(c) for c in word.body)
        new_asm.code.extend(b"\x00" * body_size)
    return word_addrs


def _primitive_addrs(new_asm: Asm) -> dict[str, int]:
    return {name.lower(): addr for name, addr in new_asm.labels.items()}


def _emit_live_strings(
    new_asm: Asm, compiler: Compiler, liveness: Liveness,
    word_addrs: dict[str, int],
) -> None:
    for label, data in compiler.string_pool.allocations:
        if label not in liveness.strings:
            continue
        word_addrs[label] = new_asm.here
        new_asm.label(label)
        for byte_value in data:
            new_asm.byte(byte_value)


def _emit_live_data_words(
    new_asm: Asm, compiler: Compiler, liveness: Liveness,
    word_addrs: dict[str, int],
) -> None:
    boundaries = _data_boundaries(compiler)
    for word in compiler.words.values():
        if word.name not in liveness.words:
            continue
        if word.kind == "constant":
            value = _extract_pusher_value(compiler, word.address)
            word_addrs[word.name] = _emit_pusher(new_asm, value)
        elif word.kind == "variable":
            data_bytes = _extract_data_bytes(compiler, word, boundaries)
            code_addr, _ = _emit_variable(new_asm, data_bytes)
            word_addrs[word.name] = code_addr


def _emit_pusher(new_asm: Asm, value: int) -> int:
    code_addr = new_asm.here
    new_asm.push_hl()
    new_asm.ld_hl_nn(value & 0xFFFF)
    new_asm.jp("NEXT")
    return code_addr


def _emit_variable(new_asm: Asm, data_bytes: bytes) -> tuple[int, int]:
    code_addr = new_asm.here
    new_asm.push_hl()
    new_asm.ld_hl_nn(0)
    fixup = len(new_asm.code) - 2
    new_asm.jp("NEXT")
    data_addr = new_asm.here
    new_asm.code[fixup] = data_addr & 0xFF
    new_asm.code[fixup + 1] = (data_addr >> 8) & 0xFF
    new_asm.code.extend(data_bytes)
    return code_addr, data_addr


def _extract_pusher_value(compiler: Compiler, code_addr: int) -> int:
    offset = code_addr - compiler.origin
    lo = compiler.asm.code[offset + 2]
    hi = compiler.asm.code[offset + 3]
    return lo | (hi << 8)


def _extract_data_bytes(
    compiler: Compiler, word: Word, boundaries: list[int],
) -> bytes:
    if word.data_address is None:
        return b""
    start = word.data_address
    end = _next_boundary_after(start, boundaries)
    return bytes(compiler.asm.code[start - compiler.origin:end - compiler.origin])


def _next_boundary_after(addr: int, boundaries: list[int]) -> int:
    for boundary in boundaries:
        if boundary > addr:
            return boundary
    raise AssertionError(f"no boundary found above address {addr:#x}")


def _data_boundaries(compiler: Compiler) -> list[int]:
    boundaries: set[int] = set()
    for word in compiler.words.values():
        if word.address is not None:
            boundaries.add(word.address)
        if word.data_address is not None:
            boundaries.add(word.data_address)
    boundaries.update(compiler.asm.labels.values())
    boundaries.add(compiler.asm.origin + len(compiler.asm.code))
    return sorted(boundaries)


def _patch_colon_bodies(
    new_asm: Asm, compiler: Compiler, liveness: Liveness,
    word_addrs: dict[str, int],
) -> None:
    for word in _live_colons(compiler, liveness):
        body_start = word_addrs[word.name] + 3
        body_bytes = ir_resolve(word.body, word_addrs, base_address=body_start)
        offset = body_start - new_asm.origin
        new_asm.code[offset:offset + len(body_bytes)] = body_bytes


def _emit_start(new_asm: Asm, compiler: Compiler, word_addrs: dict[str, int]) -> int:
    main_body_addr = new_asm.here
    new_asm.word(word_addrs["main"])
    new_asm.word(word_addrs["halt"])
    start_addr = new_asm.here
    new_asm.label("_start")
    new_asm.di()
    new_asm.ld_sp_nn(compiler.data_stack_top)
    new_asm.ld_iy_nn(compiler.return_stack_top)
    new_asm.ld_ix_nn(main_body_addr)
    new_asm.jp(word_addrs["next"])
    return start_addr


def _live_colons(compiler: Compiler, liveness: Liveness) -> list[Word]:
    return [
        word for word in compiler.words.values()
        if word.kind == "colon"
        and word.body is not None
        and word.name in liveness.words
    ]
