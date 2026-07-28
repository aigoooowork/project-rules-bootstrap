"""Apply explicitly approved analysis and final output writes safely."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from scripts.adapter_registry import safe_target_path


MANAGED_START = "<!-- project-rules-bootstrap:start -->"
MANAGED_END = "<!-- project-rules-bootstrap:end -->"
ANALYSIS_PATH = ".ai/rules.analysis.md"
WRITE_MODES = frozenset({"create", "managed-block"})


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    content: str
    mode: str


def _managed_merge(existing: str, content: str) -> str:
    if existing.count(MANAGED_START) != 1 or existing.count(MANAGED_END) != 1:
        raise ValueError("managed-block mode requires exactly one owned marker pair")
    start = existing.index(MANAGED_START)
    end = existing.index(MANAGED_END)
    if end <= start:
        raise ValueError("managed-block end marker must follow its start marker")
    prefix = existing[: start + len(MANAGED_START)]
    suffix = existing[end:]
    return "{}\n{}\n{}".format(prefix, content.strip(), suffix)


def _preflight(
    root: Path, writes: Sequence[PlannedWrite]
) -> List[Tuple[Path, str]]:
    seen = set()
    prepared: List[Tuple[Path, str]] = []
    for write in writes:
        if write.path in seen:
            raise ValueError("approved write paths must be unique")
        seen.add(write.path)
        if write.mode not in WRITE_MODES:
            raise ValueError("unsupported write mode '{}'".format(write.mode))
        if not isinstance(write.content, str):
            raise ValueError("write content must be text")
        target = safe_target_path(root, write.path)
        if write.mode == "create":
            if target.exists() or target.is_symlink():
                raise FileExistsError(
                    "refusing to overwrite existing unowned file '{}'".format(write.path)
                )
            prepared.append((target, write.content))
            continue
        if not target.is_file() or target.is_symlink():
            raise ValueError(
                "managed-block target '{}' must be an existing regular file".format(
                    write.path
                )
            )
        try:
            existing = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            raise ValueError(
                "managed-block target '{}' is not readable UTF-8".format(write.path)
            ) from error
        prepared.append((target, _managed_merge(existing, write.content)))
    return prepared


def _commit_prepared(prepared: Iterable[Tuple[Path, str]]) -> List[str]:
    changed: List[str] = []
    for target, content in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            with target.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        else:
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        changed.append(target.as_posix())
    return changed


def apply_analysis(
    root: Path,
    relative_path: str,
    content: str,
    *,
    approved: bool,
) -> List[str]:
    """Write only the exact analysis file after Gate 1 approval."""
    if not approved:
        return []
    if relative_path != ANALYSIS_PATH:
        raise ValueError("Gate 1 allows only '{}'".format(ANALYSIS_PATH))
    prepared = _preflight(
        root.resolve(strict=False),
        [PlannedWrite(relative_path, content, "create")],
    )
    _commit_prepared(prepared)
    return [relative_path]


def apply_final_outputs(
    root: Path,
    writes: Sequence[PlannedWrite],
    *,
    approved_paths: Sequence[str],
    approved: bool,
) -> List[str]:
    """Apply exactly the Gate 2 approved canonical, Manifest, and adapter set."""
    if not approved:
        return []
    planned_paths = [write.path for write in writes]
    if len(planned_paths) != len(set(planned_paths)):
        raise ValueError("final write plan contains duplicate paths")
    if set(planned_paths) != set(approved_paths) or len(planned_paths) != len(approved_paths):
        raise ValueError("final write plan must equal the exact approved path set")
    prepared = _preflight(root.resolve(strict=False), writes)
    _commit_prepared(prepared)
    return sorted(planned_paths)
