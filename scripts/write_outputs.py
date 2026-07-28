"""Apply explicitly approved analysis and final output writes safely."""

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

from scripts.adapter_registry import (
    adapter_registry_records,
    expand_registry_pattern,
    safe_target_path,
)


MANAGED_START = "<!-- project-rules-bootstrap:start -->"
MANAGED_END = "<!-- project-rules-bootstrap:end -->"
ANALYSIS_PATH = ".ai/rules.analysis.md"
MANIFEST_PATH = ".ai/rules-manifest.json"
CANONICAL_RULES_PATH = ".ai/rules"
WRITE_MODES = frozenset({"create", "replace-owned", "managed-block"})
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    content: str
    mode: str
    expected_sha256: Optional[str] = None


@dataclass(frozen=True)
class _PreparedWrite:
    root: Path
    path: str
    target: Path
    content: bytes
    mode: str
    expected_sha256: Optional[str]


@dataclass(frozen=True)
class _PriorOutputState:
    replace_owned: Dict[str, str]
    managed_paths: Set[str]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _normalized_expected_hash(value: Optional[str], path: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "write '{}' requires an exact pre-update SHA-256".format(path)
        )
    return value.lower()


def _managed_region_bounds(existing: bytes) -> tuple:
    try:
        existing.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("managed-block target is not readable UTF-8") from error
    start_marker = MANAGED_START.encode("utf-8")
    end_marker = MANAGED_END.encode("utf-8")
    if existing.count(start_marker) != 1 or existing.count(end_marker) != 1:
        raise ValueError("managed-block mode requires exactly one owned marker pair")
    start = existing.index(start_marker)
    end = existing.index(end_marker)
    if end <= start:
        raise ValueError("managed-block end marker must follow its start marker")
    return start, start + len(start_marker), end


def _managed_newline(existing: bytes, interior_start: int, interior_end: int) -> bytes:
    interior = existing[interior_start:interior_end]
    if interior.startswith(b"\r\n") or interior.endswith(b"\r\n"):
        return b"\r\n"
    if interior.startswith(b"\n") or interior.endswith(b"\n"):
        return b"\n"
    return b"\r\n" if b"\r\n" in existing else b"\n"


def _managed_merge_bytes(existing: bytes, content: str) -> bytes:
    start, interior_start, end = _managed_region_bounds(existing)
    del start
    newline = _managed_newline(existing, interior_start, end)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    body = normalized.replace("\n", newline.decode("ascii")).encode("utf-8")
    prefix = existing[:interior_start]
    suffix = existing[end:]
    return prefix + newline + body + newline + suffix


def _current_regular_file_bytes(target: Path, path: str) -> bytes:
    if not target.is_file() or target.is_symlink():
        raise ValueError("'{}' must be an existing regular file".format(path))
    try:
        return target.read_bytes()
    except OSError as error:
        raise ValueError("'{}' is not readable".format(path)) from error


def _preflight(
    root: Path,
    writes: Sequence[PlannedWrite],
    *,
    replace_owned: Optional[Dict[str, str]] = None,
    managed_paths: Optional[Set[str]] = None,
) -> List[_PreparedWrite]:
    seen = set()
    seen_targets = set()
    prepared: List[_PreparedWrite] = []
    for write in writes:
        if write.path in seen:
            raise ValueError("approved write paths must be unique")
        seen.add(write.path)
        if write.mode not in WRITE_MODES:
            raise ValueError("unsupported write mode '{}'".format(write.mode))
        if not isinstance(write.content, str):
            raise ValueError("write content must be text")
        target = safe_target_path(root, write.path)
        target_identity = os.path.normcase(str(target.resolve(strict=False)))
        if target_identity in seen_targets:
            raise ValueError("approved write paths must identify unique targets")
        seen_targets.add(target_identity)
        if write.mode == "create":
            if write.expected_sha256 is not None:
                raise ValueError(
                    "create write '{}' must not claim a prior hash".format(write.path)
                )
            if target.exists() or target.is_symlink():
                raise FileExistsError(
                    "refusing to overwrite existing unowned file '{}'".format(
                        write.path
                    )
                )
            prepared.append(
                _PreparedWrite(
                    root,
                    write.path,
                    target,
                    write.content.encode("utf-8"),
                    write.mode,
                    None,
                )
            )
            continue

        existing = _current_regular_file_bytes(target, write.path)
        expected = _normalized_expected_hash(write.expected_sha256, write.path)
        actual = _sha256(existing)
        if actual != expected:
            raise ValueError(
                "pre-update SHA-256 mismatch for '{}'".format(write.path)
            )

        if write.mode == "replace-owned":
            owned_hash = None if replace_owned is None else replace_owned.get(write.path)
            if owned_hash != expected:
                raise ValueError(
                    "replace-owned lacks validated ownership for '{}'".format(
                        write.path
                    )
                )
            content = write.content.encode("utf-8")
        else:
            if managed_paths is not None and write.path not in managed_paths:
                raise ValueError(
                    "managed-block lacks validated ownership for '{}'".format(
                        write.path
                    )
                )
            try:
                content = _managed_merge_bytes(existing, write.content)
            except ValueError as error:
                raise ValueError(
                    "managed-block target '{}': {}".format(write.path, error)
                ) from error
        prepared.append(
            _PreparedWrite(
                root,
                write.path,
                target,
                content,
                write.mode,
                expected,
            )
        )
    return prepared


def _revalidate_prepared(prepared: Iterable[_PreparedWrite]) -> None:
    for write in prepared:
        target = safe_target_path(write.root, write.path)
        if target != write.target:
            raise ValueError("write target changed for '{}'".format(write.path))
        if write.mode == "create":
            if target.exists() or target.is_symlink():
                raise FileExistsError(
                    "refusing to overwrite existing unowned file '{}'".format(
                        write.path
                    )
                )
            continue
        current = _current_regular_file_bytes(target, write.path)
        if _sha256(current) != write.expected_sha256:
            raise ValueError(
                "pre-update SHA-256 changed for '{}'".format(write.path)
            )


def _commit_prepared(prepared: Sequence[_PreparedWrite]) -> List[str]:
    _revalidate_prepared(prepared)
    changed: List[str] = []
    for write in prepared:
        if write.mode == "create":
            write.target.parent.mkdir(parents=True, exist_ok=True)
            safe_target_path(write.root, write.path)
            with write.target.open("xb") as stream:
                stream.write(write.content)
        else:
            with write.target.open("wb") as stream:
                stream.write(write.content)
        changed.append(write.path)
    return changed


def _registry_template_root(registry: object) -> Optional[Path]:
    if registry is None:
        return Path(__file__).resolve().parent.parent
    if isinstance(registry, Path):
        return (
            registry.parent.parent
            if registry.parent.name == "references"
            else registry.parent
        )
    return None


def _validated_prior_output_state(
    root: Path,
    expected_manifest_sha256: str,
    registry: object,
) -> _PriorOutputState:
    from scripts.render_adapters import render_adapter_template
    from scripts.validate_outputs import (
        _path_matches_registry_pattern,
        _resolve_adapter_registry,
        load_manifest,
        validate_output_tree,
    )

    manifest_path = safe_target_path(root, MANIFEST_PATH)
    manifest_bytes = _current_regular_file_bytes(manifest_path, MANIFEST_PATH)
    expected_manifest = _normalized_expected_hash(
        expected_manifest_sha256, MANIFEST_PATH
    )
    if _sha256(manifest_bytes) != expected_manifest:
        raise ValueError("prior Manifest SHA-256 mismatch")

    issues = validate_output_tree(root, registry)
    if issues:
        first = issues[0]
        raise ValueError(
            "prior output validation failed at '{}': {}".format(
                first.path, first.code
            )
        )
    manifest = load_manifest(manifest_path)
    registry_data = _resolve_adapter_registry(registry)
    replace_owned = {MANIFEST_PATH: expected_manifest}
    managed_paths: Set[str] = set()

    canonical_root = safe_target_path(root, CANONICAL_RULES_PATH)
    if canonical_root.is_dir() and not canonical_root.is_symlink():
        for candidate in sorted(canonical_root.rglob("*.md")):
            relative = candidate.relative_to(root).as_posix()
            target = safe_target_path(root, relative)
            content = _current_regular_file_bytes(target, relative)
            replace_owned[relative] = _sha256(content)

    if registry_data is None:
        return _PriorOutputState(replace_owned, managed_paths)

    registry_records = adapter_registry_records(registry_data)
    template_root = _registry_template_root(registry)
    for manifest_adapter in manifest.get("adapters", []):
        if not isinstance(manifest_adapter, dict):
            continue
        pattern = str(manifest_adapter["path"])
        for candidate in root.glob(expand_registry_pattern(pattern)):
            if not candidate.is_file() and not candidate.is_symlink():
                continue
            relative = candidate.relative_to(root).as_posix()
            if not _path_matches_registry_pattern(relative, pattern):
                continue
            target = safe_target_path(root, relative)
            existing = _current_regular_file_bytes(target, relative)
            try:
                _managed_region_bounds(existing)
            except ValueError:
                pass
            else:
                managed_paths.add(relative)
                continue
            record = registry_records.get(str(manifest_adapter["id"]))
            if record is None or template_root is None:
                continue
            template = safe_target_path(template_root, str(record["template"]))
            render_values = dict(record)
            render_values["consumers"] = manifest_adapter["consumers"]
            expected_content = render_adapter_template(
                template, render_values
            ).encode("utf-8")
            if existing == expected_content:
                replace_owned[relative] = _sha256(existing)

    return _PriorOutputState(replace_owned, managed_paths)


def apply_analysis(
    root: Path,
    relative_path: str,
    content: str,
    *,
    approved: bool,
    expected_sha256: Optional[str] = None,
) -> List[str]:
    """Create or safely replace only the exact analysis file after Gate 1."""
    if not approved:
        return []
    if relative_path != ANALYSIS_PATH:
        raise ValueError("Gate 1 allows only '{}'".format(ANALYSIS_PATH))
    resolved_root = root.resolve(strict=False)
    target = safe_target_path(resolved_root, relative_path)
    if target.exists() or target.is_symlink():
        expected = _normalized_expected_hash(expected_sha256, relative_path)
        write = PlannedWrite(relative_path, content, "replace-owned", expected)
        prepared = _preflight(
            resolved_root,
            [write],
            replace_owned={relative_path: expected},
        )
    else:
        if expected_sha256 is not None:
            raise ValueError("new analysis file must not claim a prior hash")
        prepared = _preflight(
            resolved_root,
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
    prior_manifest_sha256: Optional[str] = None,
    registry: object = None,
) -> List[str]:
    """Apply exactly the Gate 2 approved, ownership-validated output set."""
    if not approved:
        return []
    planned_paths = [write.path for write in writes]
    if len(planned_paths) != len(set(planned_paths)):
        raise ValueError("final write plan contains duplicate paths")
    if set(planned_paths) != set(approved_paths) or len(planned_paths) != len(
        approved_paths
    ):
        raise ValueError("final write plan must equal the exact approved path set")

    resolved_root = root.resolve(strict=False)
    manifest_target = safe_target_path(resolved_root, MANIFEST_PATH)
    prior_state: Optional[_PriorOutputState] = None
    if manifest_target.exists() or manifest_target.is_symlink():
        if prior_manifest_sha256 is None:
            raise ValueError(
                "existing output tree requires a validated prior Manifest hash"
            )
        prior_state = _validated_prior_output_state(
            resolved_root,
            prior_manifest_sha256,
            registry,
        )
    elif prior_manifest_sha256 is not None:
        raise ValueError("prior Manifest hash was supplied but no Manifest exists")

    prepared = _preflight(
        resolved_root,
        writes,
        replace_owned=None if prior_state is None else prior_state.replace_owned,
        managed_paths=None if prior_state is None else prior_state.managed_paths,
    )
    _commit_prepared(prepared)
    return sorted(planned_paths)
