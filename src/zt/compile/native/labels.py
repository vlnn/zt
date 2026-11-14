"""
Label naming for the native image, kept in one place so emitter, layout and tests agree.
"""
from __future__ import annotations

START_LABEL = "_start"
HALT_LOOP_LABEL = "__halt__"
EXECUTE_LABEL = "__execute__"


def colon_label(name: str) -> str:
    return f"__colon__{name}"


def branch_label(label_id: int) -> str:
    return f"__branch__{label_id}"


def data_label(name: str, offset: int = 0) -> str:
    return f"__data__{name}+{offset}"


def return_slot_label(name: str) -> str:
    return f"__return__{name}"


def return_operand_label(name: str) -> str:
    return f"__return_to__{name}"


def xt_wrapper_name(name: str) -> str:
    return f"__xt__{name}"
