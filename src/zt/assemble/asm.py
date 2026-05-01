"""
Z80 assembler core. Defines the `Asm` class that tracks origin, emitted bytes, labels and fixups, and gains one method per entry in `opcodes.OPCODES`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

Operand = Union[int, str]


@dataclass
class Asm:
    origin: int
    code: bytearray = field(default_factory=bytearray)
    labels: dict[str, int] = field(default_factory=dict)
    fixups: list[tuple[int, str]] = field(default_factory=list)
    rel_fixups: list[tuple[int, str]] = field(default_factory=list)
    inline_next: bool = True
    native: bool = False

    @property
    def here(self) -> int:
        """Current emission address: origin plus the number of bytes already emitted."""
        return self.origin + len(self.code)

    def label(self, name: str) -> None:
        """Bind `name` to the current address; raises on duplicates."""
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        self.labels[name] = self.here

    def alias(self, name: str, target: str) -> None:
        """Bind `name` to the same address as an already-defined label `target`."""
        if name in self.labels:
            raise ValueError(f"duplicate label: {name}")
        if target not in self.labels:
            raise KeyError(f"alias target not found: {target}")
        self.labels[name] = self.labels[target]

    def word(self, value: Operand) -> None:
        """Emit a little-endian 16-bit word; a string is recorded as a fixup and patched on `resolve`."""
        if isinstance(value, str):
            self.fixups.append((len(self.code), value))
            self.code.extend((0, 0))
        else:
            self.code.extend((value & 0xFF, (value >> 8) & 0xFF))

    def byte(self, value: int) -> None:
        self.code.append(value & 0xFF)

    def jp(self, target: Operand) -> None:
        self.code.append(0xC3)
        self.word(target)

    def jp_z(self, target: Operand) -> None:
        self.code.append(0xCA)
        self.word(target)

    def jp_nz(self, target: Operand) -> None:
        self.code.append(0xC2)
        self.word(target)

    def jp_p(self, target: Operand) -> None:
        self.code.append(0xF2)
        self.word(target)

    def jp_m(self, target: Operand) -> None:
        self.code.append(0xFA)
        self.word(target)

    def call(self, target: Operand) -> None:
        self.code.append(0xCD)
        self.word(target)

    def _emit_jr(self, opcode: int, target: str) -> None:
        """Emit a relative-jump opcode and reserve one byte for the displacement, recorded as a fixup."""
        self.code.append(opcode)
        self.rel_fixups.append((len(self.code), target))
        self.code.append(0x00)


    def jr_to(self, target: str) -> None:       self._emit_jr(0x18, target)
    def jr_nz_to(self, target: str) -> None:    self._emit_jr(0x20, target)
    def jr_z_to(self, target: str) -> None:     self._emit_jr(0x28, target)
    def jr_nc_to(self, target: str) -> None:    self._emit_jr(0x30, target)
    def jr_c_to(self, target: str) -> None:     self._emit_jr(0x38, target)
    def djnz_to(self, target: str) -> None:     self._emit_jr(0x10, target)

    def jr(self, target: str) -> None:    self.jr_to(target)
    def jr_nz(self, target: str) -> None: self.jr_nz_to(target)
    def jr_z(self, target: str) -> None:  self.jr_z_to(target)
    def jr_nc(self, target: str) -> None: self.jr_nc_to(target)
    def jr_c(self, target: str) -> None:  self.jr_c_to(target)
    def djnz(self, target: str) -> None:  self.djnz_to(target)
    def ld_c_a(self):    self.code.append(0x4F)
    def sub_e(self):     self.code.append(0x93)
    def dec_a(self):     self.code.append(0x3D)
    def jp_nz(self, target): self.code.append(0xC2); self.word(target)

    def resolve(self) -> bytes:
        """Patch all recorded fixups with real label addresses and return the final code bytes."""
        for offset, name in self.fixups:
            if name not in self.labels:
                raise KeyError(f"undefined label: {name}")
            addr = self.labels[name]
            self.code[offset] = addr & 0xFF
            self.code[offset + 1] = (addr >> 8) & 0xFF
        for offset, name in self.rel_fixups:
            if name not in self.labels:
                raise KeyError(f"undefined label: {name}")
            target_addr = self.labels[name]
            pc_after = self.origin + offset + 1
            displacement = target_addr - pc_after
            if displacement < -128 or displacement > 127:
                raise ValueError(
                    f"relative jump to {name} out of range: {displacement}"
                )
            self.code[offset] = displacement & 0xFF
        return bytes(self.code)

    def emit_next_body(self) -> None:
        """Emit the inline body of the threaded-interpreter NEXT routine (fetch, advance IX, jump)."""
        self.ld_e_ix(0)
        self.ld_d_ix(1)
        self.inc_ix()
        self.inc_ix()
        self.push_de()
        self.ret()

    def dispatch(self) -> None:
        """Tail-call NEXT: either inlined directly or via `JP NEXT`, depending on `inline_next`.
        In native mode, emit `RET` so the primitive body is a callable subroutine."""
        if self.native:
            self.ret()
            return
        if self.inline_next:
            self.emit_next_body()
        else:
            self.jp("NEXT")


def _install_opcode_methods() -> None:
    """Attach one `emit` method per `OpcodeSpec` to the `Asm` class."""
    from zt.assemble.opcodes import OPCODES
    for spec in OPCODES:
        setattr(Asm, spec.mnemonic, _method_for(spec))


def _method_for(spec):
    """Build the emitter closure for a single opcode spec, dispatched on its operand kind."""
    encoding = spec.encoding
    if spec.operand is None:
        def emit(self):
            self.code.extend(encoding)
        return emit
    if spec.operand == "n":
        def emit(self, n):
            self.code.extend(encoding)
            self.code.append(n & 0xFF)
        return emit
    if spec.operand == "d":
        def emit(self, d):
            self.code.extend(encoding)
            self.code.append(d & 0xFF)
        return emit
    if spec.operand == "nn":
        def emit(self, value):
            self.code.extend(encoding)
            self.word(value)
        return emit
    raise ValueError(f"unknown operand kind: {spec.operand!r}")


_install_opcode_methods()
