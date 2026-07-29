"""Apply explicitly approved analysis and final output writes safely."""

import hashlib
import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

from scripts.adapter_registry import (
    adapter_registry_records,
    expand_registry_pattern,
    safe_target_path,
)
from scripts.safe_fs import (
    DirectoryChain,
    MoveOutcome,
    PinnedFile,
    open_directory_chain,
    relative_exists,
    snapshot_relative,
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


@dataclass
class _PreparedWrite:
    root: Path
    path: str
    target: Path
    content: bytes
    mode: str
    expected_sha256: Optional[str]
    original_identity: Optional[tuple]
    parent_chain: Optional[DirectoryChain] = None


@dataclass
class _StagedWrite:
    prepared: _PreparedWrite
    staged_name: str
    staged_identity: tuple
    backup_name: str
    backup_identity: tuple
    claimed: bool = False
    committed: bool = False
    installed_identity: Optional[tuple] = None


@dataclass(frozen=True)
class _PriorOutputState:
    replace_owned: Dict[str, str]
    managed_paths: Set[str]
    analysis_ownership_sha256: Optional[str]


@dataclass
class _AnalysisGuard:
    chain: DirectoryChain
    pinned_file: PinnedFile
    expected_sha256: str

    def verify(self) -> None:
        parent = self.chain.parent
        parent.assert_valid()
        parent.assert_namespace()
        pinned = self.pinned_file.snapshot()
        if (
            pinned.identity != self.pinned_file.identity
            or _sha256(pinned.content) != self.expected_sha256
        ):
            raise ValueError("pinned analysis identity or SHA-256 changed")
        current = parent.snapshot("rules.analysis.md")
        if (
            current.identity != pinned.identity
            or _sha256(current.content) != self.expected_sha256
        ):
            raise ValueError(
                "analysis path changed before final Manifest commit"
            )

    def close(self) -> None:
        self.pinned_file.close()
        self.chain.close()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _regular_file_snapshot(root: Path, path: str) -> tuple:
    try:
        snapshot = snapshot_relative(root, path)
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError("'{}' must be an existing regular file".format(path)) from error
    return snapshot.content, snapshot.identity


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


def _current_regular_file_bytes(root: Path, path: str) -> bytes:
    content, _ = _regular_file_snapshot(root, path)
    return content


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
    try:
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
                try:
                    exists = relative_exists(root, write.path)
                except (OSError, ValueError, RuntimeError) as error:
                    raise ValueError(
                        "create target cannot be inspected safely for '{}'".format(
                            write.path
                        )
                    ) from error
                if exists:
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
                        None,
                    )
                )
                continue

            parts = write.path.split("/")
            parent_chain: Optional[DirectoryChain] = None
            try:
                parent_chain = open_directory_chain(root, parts[:-1])
                snapshot = parent_chain.parent.snapshot(parts[-1])
            except (OSError, ValueError, RuntimeError) as error:
                if parent_chain is not None:
                    parent_chain.close()
                raise ValueError(
                    "'{}' must be an existing safely opened regular file".format(
                        write.path
                    )
                ) from error
            existing = snapshot.content
            original_identity = snapshot.identity
            expected = _normalized_expected_hash(write.expected_sha256, write.path)
            actual = _sha256(existing)
            if actual != expected:
                parent_chain.close()
                raise ValueError(
                    "pre-update SHA-256 mismatch for '{}'".format(write.path)
                )

            if write.mode == "replace-owned":
                owned_hash = None if replace_owned is None else replace_owned.get(write.path)
                if owned_hash != expected:
                    parent_chain.close()
                    raise ValueError(
                        "replace-owned lacks validated ownership for '{}'".format(
                            write.path
                        )
                    )
                content = write.content.encode("utf-8")
            else:
                if write.path not in (managed_paths or set()):
                    parent_chain.close()
                    raise ValueError(
                        "managed-block lacks validated ownership for '{}'".format(
                            write.path
                        )
                    )
                try:
                    content = _managed_merge_bytes(existing, write.content)
                except ValueError as error:
                    parent_chain.close()
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
                    original_identity,
                    parent_chain,
                )
            )
    except BaseException:
        for item in prepared:
            if item.parent_chain is not None:
                item.parent_chain.close()
        raise
    return prepared


def _revalidate_prepared(prepared: Iterable[_PreparedWrite]) -> None:
    for write in prepared:
        chain = write.parent_chain
        if chain is None:
            raise ValueError("write parent is not safely opened for '{}'".format(write.path))
        parent = chain.parent
        parent.assert_valid()
        parent.assert_namespace()
        target_name = write.path.split("/")[-1]
        if write.mode == "create":
            if parent.exists(target_name):
                raise FileExistsError(
                    "refusing to overwrite existing unowned file '{}'".format(
                        write.path
                    )
                )
            continue
        snapshot = parent.snapshot(target_name)
        if (
            snapshot.identity != write.original_identity
            or _sha256(snapshot.content) != write.expected_sha256
        ):
            raise ValueError(
                "pre-update file identity or SHA-256 changed for '{}'".format(
                    write.path
                )
            )


def _stage_bytes(
    parent: object,
    target_name: str,
    kind: str,
    content: bytes,
) -> tuple:
    return parent.create_temporary(target_name, kind, content)


def _stage_prepared(
    prepared: Sequence[_PreparedWrite],
) -> List[_StagedWrite]:
    stages: List[_StagedWrite] = []
    try:
        for write in prepared:
            if write.parent_chain is None:
                parts = write.path.split("/")
                write.parent_chain = open_directory_chain(
                    write.root,
                    parts[:-1],
                    create=True,
                )
            parent = write.parent_chain.parent
            parent.assert_valid()
            parent.assert_namespace()
            target_name = write.path.split("/")[-1]
            staged_name, staged_identity = _stage_bytes(
                parent,
                target_name,
                "new",
                write.content,
            )
            try:
                backup_name, backup_identity = _stage_bytes(
                    parent,
                    target_name,
                    "backup",
                    b"",
                )
            except BaseException:
                parent.remove_file(
                    staged_name,
                    expected_identity=staged_identity,
                )
                raise
            stages.append(
                _StagedWrite(
                    write,
                    staged_name,
                    staged_identity,
                    backup_name,
                    backup_identity,
                )
            )
    except BaseException:
        for stage in stages:
            parent = stage.prepared.parent_chain.parent
            parent.remove_file(
                stage.staged_name,
                expected_identity=stage.staged_identity,
            )
            parent.remove_file(
                stage.backup_name,
                expected_identity=stage.backup_identity,
            )
        for write in prepared:
            if write.parent_chain is not None:
                write.parent_chain.cleanup_created()
                write.parent_chain.close()
        raise
    return stages


def _assert_parent_identity(stage: _StagedWrite) -> None:
    chain = stage.prepared.parent_chain
    if chain is None:
        raise ValueError("write parent is not open")
    chain.parent.assert_valid()
    chain.parent.assert_namespace()


def _move_with_reconciliation(
    parent: object,
    source: str,
    destination: str,
    *,
    replace: bool,
    expected_identity: tuple,
    expected_sha256: str,
) -> tuple:
    """Return ``(identity, late_error)`` after proving the actual namespace."""
    def installed_destination(outcome: object) -> Optional[tuple]:
        if not isinstance(outcome, MoveOutcome) or not outcome.destination_present:
            return None
        try:
            destination_snapshot = parent.snapshot(destination)
        except (OSError, ValueError, RuntimeError):
            return None
        if (
            destination_snapshot.identity == expected_identity
            and _sha256(destination_snapshot.content) == expected_sha256
        ):
            return destination_snapshot.identity
        return None

    try:
        outcome = parent.move(
            source,
            destination,
            replace=replace,
            expected_identity=expected_identity,
            expected_sha256=expected_sha256,
        )
    except BaseException as error:
        partial_identity = installed_destination(getattr(error, "outcome", None))
        if partial_identity is not None:
            return partial_identity, error
        try:
            destination_snapshot = parent.snapshot(destination)
            completed = (
                not parent.exists(source)
                and destination_snapshot.identity == expected_identity
                and _sha256(destination_snapshot.content) == expected_sha256
            )
        except (OSError, ValueError, RuntimeError):
            completed = False
        if completed:
            return destination_snapshot.identity, error
        raise
    if not isinstance(outcome, MoveOutcome):
        raise TypeError("namespace move did not return a mutation outcome")
    if not outcome.source_absent or not outcome.destination_present:
        partial_identity = installed_destination(outcome)
        if partial_identity is not None:
            return partial_identity, ValueError("namespace move did not complete")
        raise ValueError("namespace move did not complete")
    return outcome.identity, None


def _commit_existing_stage(stage: _StagedWrite) -> None:
    write = stage.prepared
    parent = write.parent_chain.parent
    target_name = write.path.split("/")[-1]
    _assert_parent_identity(stage)
    current = parent.snapshot(target_name)
    if (
        current.identity != write.original_identity
        or _sha256(current.content) != write.expected_sha256
    ):
        raise ValueError(
            "pre-update file identity or SHA-256 changed for '{}'".format(write.path)
        )
    _, late_error = _move_with_reconciliation(
        parent,
        target_name,
        stage.backup_name,
        replace=True,
        expected_identity=write.original_identity,
        expected_sha256=write.expected_sha256,
    )
    stage.claimed = True
    if late_error is not None:
        raise late_error
    _assert_parent_identity(stage)
    if parent.exists(target_name):
        raise ValueError("write target reappeared for '{}'".format(write.path))
    stage.installed_identity, late_error = _move_with_reconciliation(
        parent,
        stage.staged_name,
        target_name,
        replace=False,
        expected_identity=stage.staged_identity,
        expected_sha256=_sha256(write.content),
    )
    stage.committed = True
    if late_error is not None:
        raise late_error


def _commit_create_stage(stage: _StagedWrite) -> None:
    write = stage.prepared
    parent = write.parent_chain.parent
    target_name = write.path.split("/")[-1]
    _assert_parent_identity(stage)
    if parent.exists(target_name):
        raise FileExistsError(
            "refusing to overwrite existing unowned file '{}'".format(write.path)
        )
    stage.installed_identity, late_error = _move_with_reconciliation(
        parent,
        stage.staged_name,
        target_name,
        replace=False,
        expected_identity=stage.staged_identity,
        expected_sha256=_sha256(write.content),
    )
    stage.committed = True
    if late_error is not None:
        raise late_error
    _assert_parent_identity(stage)


def _rollback_stages(
    stages: Sequence[_StagedWrite],
) -> List[tuple]:
    errors: List[tuple] = []
    for stage in reversed(stages):
        try:
            parent = stage.prepared.parent_chain.parent
            parent.assert_valid()
            target_name = stage.prepared.path.split("/")[-1]
            if stage.claimed:
                if not parent.exists(stage.backup_name):
                    raise ValueError(
                        "rollback backup is missing for '{}'".format(
                            stage.prepared.path
                        )
                    )
                _move_with_reconciliation(
                    parent,
                    stage.backup_name,
                    target_name,
                    replace=True,
                    expected_identity=stage.prepared.original_identity,
                    expected_sha256=stage.prepared.expected_sha256,
                )
                stage.claimed = False
                stage.committed = False
            elif stage.committed:
                if not parent.exists(target_name):
                    raise ValueError(
                        "created rollback target is missing for '{}'".format(
                            stage.prepared.path
                        )
                    )
                _move_with_reconciliation(
                    parent,
                    target_name,
                    stage.backup_name,
                    replace=True,
                    expected_identity=stage.installed_identity,
                    expected_sha256=_sha256(stage.prepared.content),
                )
                parent.remove_file(
                    stage.backup_name,
                    expected_identity=stage.installed_identity,
                )
                stage.committed = False
        except BaseException as error:
            errors.append((stage, error))
    return errors


def _cleanup_stages(
    stages: Sequence[_StagedWrite],
    *,
    preserve_active: bool = False,
) -> List[tuple]:
    errors: List[tuple] = []
    for stage in stages:
        if preserve_active and (stage.claimed or stage.committed):
            continue
        parent = stage.prepared.parent_chain.parent
        for artifact_name, expected_identity in (
            (stage.staged_name, stage.staged_identity),
            (stage.backup_name, None),
        ):
            try:
                parent.remove_file(
                    artifact_name,
                    expected_identity=expected_identity,
                )
            except BaseException as error:
                errors.append((stage, artifact_name, error))
    return errors


def _relative_artifact_path(write_path: str, artifact_name: str) -> str:
    parent = Path(write_path).parent
    return (
        artifact_name
        if parent == Path(".")
        else (parent / artifact_name).as_posix()
    )


def _write_recovery_journal(
    prepared: Sequence[_PreparedWrite],
    rollback_errors: Sequence[tuple],
) -> tuple:
    import secrets

    root_handle = prepared[0].parent_chain.handles[0]
    entries = []
    artifacts: List[str] = []
    for stage, error in rollback_errors:
        parent = stage.prepared.parent_chain.parent
        entry = {
            "path": stage.prepared.path,
            "mode": stage.prepared.mode,
            "state": "claimed" if stage.claimed else "committed",
            "expected_sha256": stage.prepared.expected_sha256,
            "error_type": type(error).__name__,
        }
        try:
            parent.snapshot(stage.backup_name)
        except (OSError, ValueError, RuntimeError):
            pass
        else:
            backup_path = _relative_artifact_path(
                stage.prepared.path,
                stage.backup_name,
            )
            entry["backup_path"] = backup_path
            artifacts.append(backup_path)
        target_name = stage.prepared.path.split("/")[-1]
        try:
            parent.snapshot(target_name)
        except (OSError, ValueError, RuntimeError):
            pass
        else:
            entry["installed_path"] = stage.prepared.path
            artifacts.append(stage.prepared.path)
        entries.append(entry)
    journal_name = ".project-rules-bootstrap-recovery-{}.json".format(
        secrets.token_hex(12)
    )
    journal_content = (
        json.dumps(
            {
                "version": "1.0",
                "status": "manual-recovery-required",
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    root_handle.create_bytes(journal_name, journal_content)
    return journal_name, sorted(set(artifacts))


def _write_cleanup_journal(
    prepared: Sequence[_PreparedWrite],
    cleanup_errors: Sequence[tuple],
    *,
    status: str,
) -> Optional[str]:
    import secrets

    root_handle = prepared[0].parent_chain.handles[0]
    entries = []
    for stage, artifact_name, error in cleanup_errors:
        parent = stage.prepared.parent_chain.parent
        try:
            parent.snapshot(artifact_name)
        except (OSError, ValueError, RuntimeError):
            continue
        entries.append(
            {
                "path": _relative_artifact_path(
                    stage.prepared.path,
                    artifact_name,
                ),
                "write_path": stage.prepared.path,
                "error_type": type(error).__name__,
            }
        )
    if not entries:
        return None
    journal_name = ".project-rules-bootstrap-cleanup-{}.json".format(
        secrets.token_hex(12)
    )
    journal_content = (
        json.dumps(
            {
                "version": "1.0",
                "status": status,
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    root_handle.create_bytes(journal_name, journal_content)
    return journal_name


def _close_prepared_chains(prepared: Sequence[_PreparedWrite]) -> None:
    seen = set()
    for write in prepared:
        chain = write.parent_chain
        if chain is not None and id(chain) not in seen:
            seen.add(id(chain))
            chain.close()


def _commit_prepared(
    prepared: Sequence[_PreparedWrite],
    *,
    analysis_guard: Optional[_AnalysisGuard] = None,
) -> List[str]:
    stages = _stage_prepared(prepared)
    try:
        try:
            _revalidate_prepared(prepared)
            manifest_stages = [
                stage
                for stage in stages
                if stage.prepared.path == MANIFEST_PATH
            ]
            ordinary_stages = [
                stage
                for stage in stages
                if stage.prepared.path != MANIFEST_PATH
            ]
            for stage in ordinary_stages:
                if stage.prepared.mode == "create":
                    _commit_create_stage(stage)
                else:
                    _commit_existing_stage(stage)
            if analysis_guard is not None:
                analysis_guard.verify()
            for stage in manifest_stages:
                if stage.prepared.mode == "create":
                    _commit_create_stage(stage)
                else:
                    _commit_existing_stage(stage)
            if analysis_guard is not None:
                analysis_guard.verify()
        except BaseException as error:
            rollback_errors = _rollback_stages(stages)
            if rollback_errors:
                try:
                    journal, artifacts = _write_recovery_journal(
                        prepared,
                        rollback_errors,
                    )
                    recovery_labels = [journal] + artifacts
                except BaseException as journal_error:
                    recovery_labels = ["recovery journal write failed"]
                    warnings.warn(
                        "recovery journal could not be written: {}".format(
                            journal_error
                        ),
                        RuntimeWarning,
                    )
                _cleanup_stages(stages, preserve_active=True)
                raise RuntimeError(
                    "write failed; recovery artifacts retained: {}".format(
                        ", ".join(recovery_labels)
                    )
                ) from error
            cleanup_errors = _cleanup_stages(stages)
            if cleanup_errors:
                try:
                    _write_cleanup_journal(
                        prepared,
                        cleanup_errors,
                        status="rolled-back-cleanup-required",
                    )
                except BaseException as cleanup_journal_error:
                    warnings.warn(
                        "rollback cleanup journal could not be written: {}".format(
                            cleanup_journal_error
                        ),
                        RuntimeWarning,
                    )
            for write in prepared:
                if write.parent_chain is not None:
                    write.parent_chain.cleanup_created()
            raise

        cleanup_errors = _cleanup_stages(stages)
        if cleanup_errors:
            try:
                journal = _write_cleanup_journal(
                    prepared,
                    cleanup_errors,
                    status="committed-cleanup-required",
                )
            except BaseException as cleanup_journal_error:
                warnings.warn(
                    "committed cleanup journal could not be written: {}".format(
                        cleanup_journal_error
                    ),
                    RuntimeWarning,
                )
            else:
                if journal is not None:
                    warnings.warn(
                        "commit completed; cleanup artifacts are recorded in '{}'".format(
                            journal
                        ),
                        RuntimeWarning,
                    )
        return [write.path for write in prepared]
    finally:
        _close_prepared_chains(prepared)


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
        _canonical_rule_files,
        _path_matches_registry_pattern,
        _resolve_adapter_registry,
        validate_output_tree,
        validate_manifest_data,
    )

    manifest_path = safe_target_path(root, MANIFEST_PATH)
    manifest_bytes = _current_regular_file_bytes(root, MANIFEST_PATH)
    expected_manifest = _normalized_expected_hash(
        expected_manifest_sha256, MANIFEST_PATH
    )
    if _sha256(manifest_bytes) != expected_manifest:
        raise ValueError("prior Manifest SHA-256 mismatch")
    try:
        manifest = validate_manifest_data(
            json.loads(manifest_bytes.decode("utf-8"))
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("prior Manifest is invalid") from error

    # Gate 1 deliberately makes the old ownership ledger temporarily stale.
    # Validate the rest of the prior output tree here, then enforce analysis
    # ownership separately against the exact Manifest snapshot read above.
    issues = validate_output_tree(
        root,
        registry,
        check_analysis_ownership=False,
    )
    if issues:
        first = issues[0]
        raise ValueError(
            "prior output validation failed at '{}': {}".format(
                first.path, first.code
            )
        )
    registry_data = _resolve_adapter_registry(registry)
    replace_owned = {MANIFEST_PATH: expected_manifest}
    managed_paths: Set[str] = set()
    ownership = manifest.get("analysis_ownership")
    analysis_ownership_sha256 = (
        str(ownership["sha256"])
        if isinstance(ownership, dict)
        else None
    )

    canonical_files, canonical_path_issues = _canonical_rule_files(root)
    if canonical_path_issues:
        first = canonical_path_issues[0]
        raise ValueError(
            "prior canonical path validation failed at '{}': {}".format(
                first.path,
                first.code,
            )
        )
    for candidate in canonical_files:
        relative = candidate.path.relative_to(root).as_posix()
        content = _current_regular_file_bytes(root, relative)
        replace_owned[relative] = _sha256(content)

    if registry_data is None:
        return _PriorOutputState(
            replace_owned,
            managed_paths,
            analysis_ownership_sha256,
        )

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
            existing = _current_regular_file_bytes(root, relative)
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

    return _PriorOutputState(
        replace_owned,
        managed_paths,
        analysis_ownership_sha256,
    )


def _authorized_new_managed_paths(
    writes: Sequence[PlannedWrite],
    registry: object,
) -> Set[str]:
    managed_writes = [write for write in writes if write.mode == "managed-block"]
    if not managed_writes:
        return set()
    manifest_writes = [write for write in writes if write.path == MANIFEST_PATH]
    if len(manifest_writes) != 1 or manifest_writes[0].mode != "create":
        raise ValueError(
            "initial managed-block writes require one new validated Manifest"
        )
    try:
        manifest_data = json.loads(manifest_writes[0].content)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("new Manifest is not valid JSON") from error

    from scripts.validate_outputs import (
        _manifest_adapter_issues,
        _path_matches_registry_pattern,
        _resolve_adapter_registry,
        validate_manifest_data,
    )

    try:
        manifest = validate_manifest_data(manifest_data)
        registry_data = _resolve_adapter_registry(registry)
    except ValueError as error:
        raise ValueError("new Manifest or adapter registry is invalid") from error
    if registry_data is None:
        raise ValueError("managed-block writes require an authoritative registry")
    manifest_issues, authorized = _manifest_adapter_issues(manifest, registry_data)
    if manifest_issues:
        first = manifest_issues[0]
        raise ValueError(
            "new Manifest adapter authorization failed: {}".format(first.code)
        )

    managed_paths: Set[str] = set()
    for write in managed_writes:
        matching = [
            adapter
            for adapter in authorized
            if adapter.get("support") != "unverified"
            and _path_matches_registry_pattern(write.path, str(adapter["path"]))
        ]
        if len(matching) != 1:
            raise ValueError(
                "managed-block path '{}' is not authorized by the new Manifest "
                "and registry".format(write.path)
            )
        managed_paths.add(write.path)
    return managed_paths


def _validate_planned_analysis_ownership(
    root: Path,
    writes: Sequence[PlannedWrite],
) -> Optional[_AnalysisGuard]:
    """Bind the final Manifest ledger to the current Gate 1 analysis bytes."""
    if any(write.path == ANALYSIS_PATH for write in writes):
        raise ValueError("Gate 2 must not write the Gate 1 analysis path")

    manifest_writes = [
        write for write in writes if write.path == MANIFEST_PATH
    ]
    if manifest_writes:
        manifest_bytes = manifest_writes[0].content.encode("utf-8")
    else:
        try:
            manifest_exists = relative_exists(root, MANIFEST_PATH)
        except (OSError, ValueError, RuntimeError) as error:
            raise ValueError("Manifest path cannot be inspected safely") from error
        if not manifest_exists:
            manifest_bytes = None
        else:
            manifest_bytes = _current_regular_file_bytes(root, MANIFEST_PATH)

    if manifest_bytes is None:
        manifest = None
    else:
        from scripts.validate_outputs import validate_manifest_data

        try:
            manifest = validate_manifest_data(
                json.loads(manifest_bytes.decode("utf-8"))
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                "final Manifest cannot establish analysis ownership"
            ) from error

    ownership = (
        manifest.get("analysis_ownership")
        if isinstance(manifest, dict)
        else None
    )
    analysis_chain: Optional[DirectoryChain] = None
    try:
        analysis_chain = open_directory_chain(root, [".ai"])
    except FileNotFoundError:
        analysis_exists = False
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError("analysis path cannot be inspected safely") from error
    else:
        analysis_exists = analysis_chain.parent.exists("rules.analysis.md")

    if not analysis_exists:
        if analysis_chain is not None:
            analysis_chain.close()
        if ownership is not None:
            raise ValueError(
                "final Manifest records analysis ownership but the file is absent"
            )
        return None
    if not isinstance(ownership, dict):
        analysis_chain.close()
        raise ValueError(
            "final Manifest must record the approved analysis ownership provenance"
        )
    pinned_file: Optional[PinnedFile] = None
    try:
        pinned_file = analysis_chain.parent.pin_file("rules.analysis.md")
        pinned = pinned_file.snapshot()
        actual = _sha256(pinned.content)
    except (OSError, ValueError, RuntimeError) as error:
        if pinned_file is not None:
            pinned_file.close()
        analysis_chain.close()
        raise ValueError("analysis path cannot be pinned safely") from error
    if ownership.get("sha256") != actual:
        pinned_file.close()
        analysis_chain.close()
        raise ValueError(
            "final Manifest analysis ownership SHA-256 does not match "
            "the approved analysis"
        )
    return _AnalysisGuard(analysis_chain, pinned_file, actual)


def apply_analysis(
    root: Path,
    relative_path: str,
    content: str,
    *,
    approved: bool,
    expected_sha256: Optional[str] = None,
    prior_manifest_sha256: Optional[str] = None,
    registry: object = None,
) -> List[str]:
    """Create or safely replace only the exact analysis file after Gate 1."""
    if not approved:
        return []
    if relative_path != ANALYSIS_PATH:
        raise ValueError("Gate 1 allows only '{}'".format(ANALYSIS_PATH))
    resolved_root = root.resolve(strict=False)
    safe_target_path(resolved_root, relative_path)
    try:
        target_exists = relative_exists(resolved_root, relative_path)
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError("analysis path cannot be inspected safely") from error
    if target_exists:
        if prior_manifest_sha256 is None:
            raise ValueError(
                "existing analysis requires validated prior Manifest provenance"
            )
        prior_state = _validated_prior_output_state(
            resolved_root,
            prior_manifest_sha256,
            registry,
        )
        owned_hash = prior_state.analysis_ownership_sha256
        if owned_hash is None:
            raise ValueError(
                "existing analysis has no persistent ownership provenance; "
                "migrate it or re-confirm ownership before replacement"
            )
        current = _current_regular_file_bytes(resolved_root, relative_path)
        current_hash = _sha256(current)
        if current_hash != owned_hash:
            raise ValueError(
                "existing analysis does not match its Manifest ownership provenance; "
                "re-confirm ownership before replacement"
            )
        expected = _normalized_expected_hash(expected_sha256, relative_path)
        if expected != owned_hash:
            raise ValueError(
                "analysis pre-update SHA-256 does not match ownership provenance"
            )
        write = PlannedWrite(relative_path, content, "replace-owned", expected)
        prepared = _preflight(
            resolved_root,
            [write],
            replace_owned={relative_path: owned_hash},
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
    safe_target_path(resolved_root, MANIFEST_PATH)
    prior_state: Optional[_PriorOutputState] = None
    try:
        manifest_exists = relative_exists(resolved_root, MANIFEST_PATH)
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError("Manifest path cannot be inspected safely") from error
    if manifest_exists:
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
    analysis_guard = _validate_planned_analysis_ownership(
        resolved_root,
        writes,
    )
    try:
        managed_paths = (
            prior_state.managed_paths
            if prior_state is not None
            else _authorized_new_managed_paths(writes, registry)
        )
        prepared = _preflight(
            resolved_root,
            writes,
            replace_owned=(
                None if prior_state is None else prior_state.replace_owned
            ),
            managed_paths=managed_paths,
        )
        _commit_prepared(prepared, analysis_guard=analysis_guard)
    finally:
        if analysis_guard is not None:
            analysis_guard.close()
    return sorted(planned_paths)
