"""
Lays out the native image: start stub, colon words, the out-of-line primitives they
call, strings and data. Then points the compiler's dictionary at the new addresses so
map, profile and test tooling keep working.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from zt.assemble.asm import Asm
from zt.assemble.primitive_blob import PrimitiveBlob, emit_blob
from zt.compile.native.emitter import ColonEmitter, Requirements
from zt.compile.native.labels import (
    EXECUTE_LABEL,
    HALT_LOOP_LABEL,
    START_LABEL,
    colon_label,
    data_label,
    xt_wrapper_name,
)
from zt.compile.native.plan import NativePlan, plan_native
from zt.compile.tree_shake import _data_boundaries, _extract_data_bytes

if TYPE_CHECKING:
    from zt.compile.compiler import Compiler, Word

ASM_WORD_REFERENCE = "__word__"
ASM_DATA_REFERENCE = "__word_data__"


def build_native_image(compiler: Compiler) -> tuple[bytes, int]:
    plan = plan_native(compiler)
    asm = Asm(origin=compiler.origin)
    requirements = Requirements()
    _emit_start(asm, compiler, plan)
    _emit_colons(asm, plan, requirements)
    _emit_out_of_line_primitives(asm, plan, requirements)
    _emit_execute_trampoline(asm, requirements)
    _emit_strings(asm, compiler, plan)
    data_addrs = _emit_data(asm, compiler, plan)
    _bind_data_labels(asm, requirements, data_addrs)
    _bind_asm_word_references(asm, plan, data_addrs)
    _patch_ticked_data(asm, compiler, plan, data_addrs)
    image = asm.resolve()
    _commit(compiler, asm, plan, data_addrs)
    return image, asm.labels[START_LABEL]


def _emit_start(asm: Asm, compiler: Compiler, plan: NativePlan) -> None:
    asm.label(START_LABEL)
    asm.di()
    asm.ld_sp_nn(compiler.data_stack_top)
    asm.ld_iy_nn(compiler.return_stack_top)
    asm.call(colon_label(plan.main))
    asm.label(HALT_LOOP_LABEL)
    asm.halt()
    asm.jr_to(HALT_LOOP_LABEL)


def _emit_colons(asm: Asm, plan: NativePlan, requirements: Requirements) -> None:
    emitter = ColonEmitter(asm, plan.resolver, requirements)
    for name, cells in plan.bodies.items():
        emitter.emit(name, cells, plan.conventions[name])


def _emit_out_of_line_primitives(
    asm: Asm, plan: NativePlan, requirements: Requirements,
) -> None:
    for blob in _blobs_with_dependencies(plan, requirements):
        emit_blob(asm, blob)


def _blobs_with_dependencies(
    plan: NativePlan, requirements: Requirements,
) -> list[PrimitiveBlob]:
    ordered: dict[int, PrimitiveBlob] = {}
    pending = [prim.blob for prim in requirements.out_of_line.values()]
    while pending:
        blob = pending.pop(0)
        if id(blob) in ordered:
            continue
        ordered[id(blob)] = blob
        pending.extend(_dependency_blobs(plan, blob))
    return list(ordered.values())


def _dependency_blobs(plan: NativePlan, blob: PrimitiveBlob) -> list[PrimitiveBlob]:
    return [
        _blob_defining(plan, dep)
        for dep in sorted(blob.external_deps)
        if not dep.startswith((ASM_WORD_REFERENCE, ASM_DATA_REFERENCE))
    ]


def _blob_defining(plan: NativePlan, label: str) -> PrimitiveBlob:
    prim = plan.resolver.primitives.get(label)
    if prim is None:
        raise NotImplementedError(
            f"out-of-line primitive depends on unknown label {label!r}"
        )
    return prim.blob


def _emit_execute_trampoline(asm: Asm, requirements: Requirements) -> None:
    if not requirements.execute:
        return
    asm.label(EXECUTE_LABEL)
    asm.push_de()
    asm.ret()


def _emit_strings(asm: Asm, compiler: Compiler, plan: NativePlan) -> None:
    for label, data in compiler.string_pool.allocations:
        if label in plan.liveness.strings:
            asm.label(label)
            asm.code.extend(data)


def _emit_data(asm: Asm, compiler: Compiler, plan: NativePlan) -> dict[str, int]:
    boundaries = _data_boundaries(compiler)
    data_addrs: dict[str, int] = {}
    for word in _live_data_words(compiler, plan):
        if word.bank is not None:
            data_addrs[word.name] = word.data_address
            continue
        data_addrs[word.name] = asm.here
        asm.code.extend(_extract_data_bytes(compiler, word, boundaries))
    return data_addrs


def _live_data_words(compiler: Compiler, plan: NativePlan) -> list[Word]:
    return [
        word for word in compiler.words.values()
        if word.kind == "variable" and word.name in plan.liveness.words
    ]


def _bind_data_labels(
    asm: Asm, requirements: Requirements, data_addrs: dict[str, int],
) -> None:
    for name, offset in requirements.data_refs:
        asm.labels[data_label(name, offset)] = (data_addrs[name] + offset) & 0xFFFF


def _bind_asm_word_references(
    asm: Asm, plan: NativePlan, data_addrs: dict[str, int],
) -> None:
    for label in {name for _, name in asm.fixups} - set(asm.labels):
        if label.startswith(ASM_DATA_REFERENCE):
            asm.labels[label] = data_addrs[label[len(ASM_DATA_REFERENCE):]]
        elif label.startswith(ASM_WORD_REFERENCE):
            asm.labels[label] = _entry_address(asm, plan, label[len(ASM_WORD_REFERENCE):])


def _entry_address(asm: Asm, plan: NativePlan, name: str) -> int:
    entry = name if name in plan.bodies else xt_wrapper_name(name)
    return asm.labels[colon_label(entry)]


def _patch_ticked_data(
    asm: Asm, compiler: Compiler, plan: NativePlan, data_addrs: dict[str, int],
) -> None:
    for ref in compiler._word_address_refs:
        if ref.owner not in data_addrs:
            continue
        owner = compiler.words.definition(ref.owner)
        at = data_addrs[ref.owner] + (ref.asm_addr - owner.data_address) - asm.origin
        target = _ticked_address(asm, plan, data_addrs, ref.target)
        asm.code[at] = target & 0xFF
        asm.code[at + 1] = (target >> 8) & 0xFF


def _ticked_address(
    asm: Asm, plan: NativePlan, data_addrs: dict[str, int], target: str,
) -> int:
    if target in data_addrs:
        return data_addrs[target]
    return _entry_address(asm, plan, target)


def _commit(
    compiler: Compiler, asm: Asm, plan: NativePlan, data_addrs: dict[str, int],
) -> None:
    from zt.compile.compiler import Word
    compiler.asm = asm
    compiler.emitter.source_map = []
    for name in [n for n in compiler.words if n not in plan.liveness.words]:
        del compiler.words[name]
    for name, word in list(compiler.words.items()):
        compiler.words[name] = _relocated(word, asm, data_addrs)
    compiler.words[START_LABEL] = Word(
        name=START_LABEL, address=asm.labels[START_LABEL], kind="prim",
    )


def _relocated(word: Word, asm: Asm, data_addrs: dict[str, int]) -> Word:
    if word.name in data_addrs:
        addr = data_addrs[word.name]
        return replace(word, address=addr, data_address=addr)
    if word.kind == "colon":
        return replace(word, address=asm.labels.get(colon_label(word.name), 0))
    return replace(word, address=_primitive_address(word, asm))


def _primitive_address(word: Word, asm: Asm) -> int:
    if word.kind != "prim":
        return 0
    return asm.labels.get(word.name, asm.labels.get(word.name.upper(), 0))
