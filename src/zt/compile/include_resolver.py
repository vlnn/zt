"""
`INCLUDE` / `REQUIRE` path resolution: searches relative to the including file, then the configured include dirs, then the bundled stdlib dir. Deduplicates already-loaded sources.
"""
from __future__ import annotations

from pathlib import Path


class IncludeNotFound(Exception):
    pass


class IncludeResolver:

    def __init__(
        self,
        include_dirs: list[Path],
        bundled_stdlib_dir: Path | None = None,
    ) -> None:
        self.include_dirs: list[Path] = [Path(d) for d in include_dirs]
        self.bundled_stdlib_dir: Path | None = (
            Path(bundled_stdlib_dir) if bundled_stdlib_dir is not None else None
        )
        self._seen: set[Path] = set()

    def resolve(self, filename: str, source_path: Path) -> Path:
        given = Path(filename)
        if given.is_absolute():
            return self._resolve_absolute(given, filename)
        return self._resolve_relative(filename, source_path)

    def has_seen(self, path: Path) -> bool:
        return path in self._seen

    def mark_seen(self, path: Path) -> None:
        self._seen.add(path)

    def seen_paths(self) -> frozenset[Path]:
        return frozenset(self._seen)

    def _resolve_absolute(self, given: Path, filename: str) -> Path:
        if given.is_file():
            return given.resolve()
        raise IncludeNotFound(f"include: cannot find '{filename}'")

    def _resolve_relative(self, filename: str, source_path: Path) -> Path:
        candidates = self._candidate_paths(filename, source_path)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise IncludeNotFound(self._not_found_message(filename, candidates))

    def _candidate_paths(self, filename: str, source_path: Path) -> list[Path]:
        candidates: list[Path] = []
        if source_path.is_file():
            candidates.append(source_path.parent / filename)
        candidates.extend(d / filename for d in self.include_dirs)
        if self.bundled_stdlib_dir is not None:
            candidates.append(self.bundled_stdlib_dir / filename)
        return candidates

    def _not_found_message(self, filename: str, candidates: list[Path]) -> str:
        searched = "\n  ".join(str(p) for p in candidates) or "(no search paths)"
        return f"include: cannot find '{filename}'; searched:\n  {searched}"
