"""Generate a 64-entry sine table as 8.8-fixed cells for inclusion in voxel.fs.

Each entry: round(sin(i * 2*pi / 64) * 256), in [-256, +256].
"""
import math


def gen_sine_table(n: int = 64, scale: int = 256) -> list[int]:
    return [round(math.sin(i * 2 * math.pi / n) * scale) for i in range(n)]


def emit_forth(values: list[int]) -> str:
    rows = []
    for i in range(0, len(values), 8):
        chunk = values[i:i + 8]
        rows.append("    " + " ".join(f"{v:>5d}" for v in chunk))
    return "w: sine64\n" + "\n".join(rows) + "\n;"


if __name__ == "__main__":
    print(emit_forth(gen_sine_table()))
