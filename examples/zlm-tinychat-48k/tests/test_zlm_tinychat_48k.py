"""Layout invariants and end-to-end runtime test for the 48K port of zlm-tinychat.

The port hoists the big activations (acts0, acts1, acts2) above the image,
parks acts3 in the 48K printer-buffer area at $5B00 (invisible to the
display), and inlines a minimal stdlib so the small per-layer buffers and
scalar variables fit in the image. Tests pin the arithmetic so a future
image-size regression fails loudly, and run the SNA in the simulator to
confirm the model still answers "HELLO" with "HI".
"""
import sys
from pathlib import Path

import pytest

EXAMPLE_DIR = Path(__file__).resolve().parents[1]
ROOT = EXAMPLE_DIR.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zt.compile.compiler import Compiler
from zt.sim import (
    SPECTRUM_FONT_BASE,
    TEST_FONT,
    Z80,
    decode_screen_text,
)

ORIGIN = 0x5CB6
RSTACK_TOP = 0xFFA0
DSTACK_TOP = 0xFFC0
RSTACK_BUDGET = 64
DSTACK_BUDGET = 32

ACTS3_LO, ACTS3_HI = 0x5B00, 0x5C00
ACTS2_LO, ACTS2_HI = 0xF9E0, 0xFB60
ACTS0_LO, ACTS0_HI = 0xFB60, 0xFD60
ACTS1_LO, ACTS1_HI = 0xFD60, 0xFF60

IMAGE_END_MAX = ACTS2_LO


@pytest.fixture(scope="module")
def example_dir() -> Path:
    return EXAMPLE_DIR


@pytest.fixture(scope="module")
def compiled(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    c.build_tree_shaken()
    return c


def test_no_bank_data_is_emitted(compiled) -> None:
    assert not compiled.banks(), (
        "48K port should not emit any bank data; in-bank/end-bank were dropped"
    )


def test_image_ends_below_acts2(compiled) -> None:
    image_end = ORIGIN + len(compiled.asm.code)
    headroom = IMAGE_END_MAX - image_end
    assert image_end <= IMAGE_END_MAX, (
        f"tree_shaken image ends ${image_end:04X}; must not cross ${IMAGE_END_MAX:04X} "
        f"(acts2 lives there). headroom={headroom:+d} bytes"
    )


def test_acts3_is_invisible_to_display() -> None:
    """acts3 at $5B00..$5C00 sits in the 48K printer-buffer area; the screen
    pixel area ($4000..$57FF) and attrs ($5800..$5AFF) never touch it."""
    assert ACTS3_HI <= 0x5C00, "acts3 should not extend into image area"
    assert ACTS3_LO >= 0x5B00, (
        f"acts3 should sit at or above $5B00 to stay out of screen attrs; "
        f"got ${ACTS3_LO:04X}"
    )


@pytest.mark.parametrize(
    "name,lo,hi",
    [
        ("acts3", ACTS3_LO, ACTS3_HI),
        ("acts2", ACTS2_LO, ACTS2_HI),
        ("acts0", ACTS0_LO, ACTS0_HI),
        ("acts1", ACTS1_LO, ACTS1_HI),
    ],
)
def test_buffer_outside_image(compiled, name, lo, hi) -> None:
    image_end = ORIGIN + len(compiled.asm.code)
    above_image = lo >= image_end
    below_image = hi <= ORIGIN
    assert above_image or below_image, (
        f"buffer {name} (${lo:04X}..${hi:04X}) should not overlap tree_shaken image "
        f"(${ORIGIN:04X}..${image_end:04X})"
    )


def test_origin_clears_system_variables() -> None:
    """Spectrum 48K system variables span $5C00..$5CB6. The ROM IM 1 handler
    increments FRAMES at $5C78 every 50Hz; if our image overlaps that byte,
    any interrupt that fires (e.g. some loaders re-enable interrupts during
    SNA load) corrupts a primitive body and crashes the program. Origin
    must sit at or above $5CB6 so this can never happen."""
    SYSVARS_END = 0x5CB6
    assert ORIGIN >= SYSVARS_END, (
        f"origin ${ORIGIN:04X} should be >= ${SYSVARS_END:04X} to clear the "
        f"Spectrum system-variable area; otherwise IM 1 corrupts FRAMES at "
        f"$5C78 and crashes any code/data living there"
    )


def test_acts1_clears_rstack_region() -> None:
    rstack_floor = RSTACK_TOP - RSTACK_BUDGET
    assert ACTS1_HI <= rstack_floor, (
        f"acts1 ends ${ACTS1_HI:04X}; rstack region starts ${rstack_floor:04X}"
    )


def test_rstack_clears_dstack_region() -> None:
    dstack_floor = DSTACK_TOP - DSTACK_BUDGET
    assert RSTACK_TOP <= dstack_floor, (
        f"rstack-top ${RSTACK_TOP:04X} should not collide with dstack region "
        f"(starts ${dstack_floor:04X})"
    )


@pytest.fixture(scope="module")
def screen_text(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    image, start = c.build_tree_shaken()

    m = Z80(mode="48k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = start
    m.input_buffer = bytearray(b"HELLO\r")
    m.run(max_ticks=80_000_000)

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0)
    return raw.decode("ascii", errors="replace")


@pytest.mark.slow
def test_rstack_peak_within_budget() -> None:
    """Pin peak return-stack usage during a HELLO query.

    The 32-byte rstack budget originally allocated for this port left only
    6 bytes of margin between peak rstack and the top of acts1 ($FF60).
    Widening to 64 bytes via `--rstack 0xFFA0` (consuming the previously-
    unused gap) gives a 38-byte margin at the same peak usage. This test
    pins both the peak and the headroom so future changes that grow stack
    pressure fail loudly rather than silently corrupting acts1.
    """
    src = (EXAMPLE_DIR / "main.fs").read_text()
    c = Compiler(
        include_dirs=[EXAMPLE_DIR, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    image, start = c.build_tree_shaken()

    m = Z80(mode="48k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = start
    m.input_buffer = bytearray(b"HELLO\r")

    iy_min = RSTACK_TOP
    elapsed = 0
    target_ticks = 30_000_000
    while elapsed < target_ticks and not m.halted:
        m.run(max_ticks=15_000)
        elapsed += 15_000
        iy_min = min(iy_min, m.iy)

    peak_rstack = RSTACK_TOP - iy_min
    margin_to_acts1 = iy_min - ACTS1_HI

    assert peak_rstack <= 32, (
        f"peak return-stack usage during HELLO query was {peak_rstack} bytes; "
        f"a regression above 32 bytes suggests deeper recursion that the "
        f"original 32-byte budget could not contain"
    )
    assert margin_to_acts1 >= 16, (
        f"margin between peak rstack (${iy_min:04X}) and acts1 (${ACTS1_HI:04X}) "
        f"is {margin_to_acts1} bytes; want at least 16 bytes (8 cells) of "
        f"headroom to absorb deeper queries without corrupting acts1"
    )


@pytest.mark.slow
def test_query_appears_on_first_line(screen_text) -> None:
    assert "HELLO" in screen_text, (
        f"the typed query 'HELLO' should appear on screen; got:\n{screen_text}"
    )


@pytest.mark.slow
def test_response_is_HI(screen_text) -> None:
    lines = [ln for ln in screen_text.split("\r") if ln.strip()]
    non_query_lines = [ln for ln in lines if "HELLO" not in ln]
    assert non_query_lines, (
        f"after the query line there should be a response line; full screen:\n"
        f"{screen_text}"
    )
    response = non_query_lines[0].strip()
    assert response == "HI", (
        f"48K port should answer 'HELLO' with 'HI' (same as 128K reference); "
        f"got {response!r}; full screen:\n{screen_text}"
    )


# --- tree-shaking tests ---------------------------------------------------


@pytest.fixture(scope="module")
def tree_shaken_compiler(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    c.build_tree_shaken()
    return c


def test_tree_shaken_image_ends_below_acts2(compiled, tree_shaken_compiler) -> None:
    tree_shaken_end = ORIGIN + len(tree_shaken_compiler.asm.code)
    assert tree_shaken_end < IMAGE_END_MAX, (
        f"tree_shaken image must end below acts2 (${IMAGE_END_MAX:04X}); "
        f"got ${tree_shaken_end:04X}"
    )


def test_tree_shaking_shrinks_image_relative_to_eager(compiled, tree_shaken_compiler) -> None:
    """Tree-shaking must produce a smaller image than the un-tree_shaken build.

    At origin=$5CB6 the eager image overflows past acts2, so tree-shaking is
    required for the 48K port to fit. This test pins that tree-shaking still
    delivers the underlying size win regardless of whether either build
    happens to fit at the chosen origin.
    """
    eager_size = len(compiled._main_asm.code)
    tree_shaken_size = len(tree_shaken_compiler.asm.code)
    assert tree_shaken_size < eager_size, (
        f"tree-shaking should shrink the image: "
        f"eager_size={eager_size}, tree_shaken_size={tree_shaken_size}"
    )


def test_tree_shaking_yields_substantial_headroom(tree_shaken_compiler) -> None:
    tree_shaken_end = ORIGIN + len(tree_shaken_compiler.asm.code)
    headroom = IMAGE_END_MAX - tree_shaken_end
    assert headroom >= 500, (
        f"tree-shaking should provide at least 500 bytes of headroom for future "
        f"feature work; got {headroom} bytes"
    )


@pytest.mark.slow
def test_survives_simulated_im1_corruption() -> None:
    """Pin: the production build (origin=$5CB6, --tree-shake) is robust against
    Spectrum ROM IM 1 interrupts corrupting the FRAMES byte at $5C78.

    On real hardware, some loaders re-enable interrupts during SNA load.
    Even with DI at _start, one or more interrupts can fire before DI
    executes, incrementing FRAMES at $5C78. With the original origin=$5C00,
    that byte lay inside R> primitive code and the next R> call crashed.
    With origin=$5CB6, $5C78 is below image-start and any FRAMES corruption
    is harmless. This test simulates the corruption loop and pins the
    invariant: HELLO query still returns HI even when $5C78 is being
    overwritten throughout execution.
    """
    src = (EXAMPLE_DIR / "main.fs").read_text()
    c = Compiler(
        include_dirs=[EXAMPLE_DIR, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    image, start = c.build_tree_shaken()

    m = Z80(mode="48k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = start
    m.input_buffer = bytearray(b"HELLO\r")

    interrupt_period = 70_000
    total = 0
    last_int = 0
    target_ticks = 40_000_000
    while total < target_ticks and not m.halted:
        m.run(max_ticks=20_000)
        total += 20_000
        if total - last_int >= interrupt_period:
            m.mem[0x5C78] = (m.mem[0x5C78] + 1) & 0xFF
            if m.mem[0x5C78] == 0:
                m.mem[0x5C79] = (m.mem[0x5C79] + 1) & 0xFF
            last_int = total

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0).decode(
        "ascii", errors="replace",
    )
    assert "HELLO" in raw, (
        f"echoed input HELLO should still appear despite FRAMES corruption; "
        f"screen={raw[:80]!r}"
    )
    assert "HI" in raw, (
        f"chat should still answer HI despite FRAMES corruption; "
        f"screen={raw[:80]!r}"
    )


@pytest.fixture(scope="module")
def tree_shaken_screen_text(example_dir):
    src = (example_dir / "main.fs").read_text()
    c = Compiler(
        include_dirs=[example_dir, ROOT / "stdlib"],
        origin=ORIGIN,
        data_stack_top=DSTACK_TOP,
        return_stack_top=RSTACK_TOP,
        inline_next=False,
    )
    c.compile_source(src, "main.fs")
    c.compile_main_call()
    image, start_addr = c.build_tree_shaken()

    m = Z80(mode="48k")
    m.load(c.origin, image)
    m.load(SPECTRUM_FONT_BASE, TEST_FONT)
    m.pc = start_addr
    m.input_buffer = bytearray(b"HELLO\r")
    m.run(max_ticks=80_000_000)

    raw = decode_screen_text(m.mem, cursor_row=23, cursor_col=0)
    return raw.decode("ascii", errors="replace")


@pytest.mark.slow
def test_tree_shaken_query_appears_on_first_line(tree_shaken_screen_text) -> None:
    assert "HELLO" in tree_shaken_screen_text, (
        f"the typed query 'HELLO' should appear on screen in the tree_shaken image; "
        f"got:\n{tree_shaken_screen_text}"
    )


@pytest.mark.slow
def test_tree_shaken_response_is_HI(tree_shaken_screen_text) -> None:
    lines = [ln for ln in tree_shaken_screen_text.split("\r") if ln.strip()]
    non_query_lines = [ln for ln in lines if "HELLO" not in ln]
    assert non_query_lines, (
        f"after the query line there should be a response line; full screen:\n"
        f"{tree_shaken_screen_text}"
    )
    response = non_query_lines[0].strip()
    assert response == "HI", (
        f"tree_shaken 48K port should still answer 'HELLO' with 'HI'; "
        f"got {response!r}; full screen:\n{tree_shaken_screen_text}"
    )
