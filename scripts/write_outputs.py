"""Apply one confirmed, preflighted output plan with the manifest installed last."""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Optional, Sequence

from scripts.manifest import load_manifest, owned_file_hashes, validate_manifest_data


MANIFEST_PATH = ".ai/rules-manifest.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WRITE_MODES = {"create", "replace-owned", "delete-owned"}
SENSITIVE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets",
    "secrets.json",
}


@dataclass(frozen=True)
class PlannedWrite:
    path: str
    content: Optional[str]
    mode: str
    expected_sha256: Optional[str] = None


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_relative_path(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "\x00" in value
        or ":" in value
    ):
        raise ValueError("write path must be a safe relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("write path must be a safe relative POSIX path")
    if any(part.lower() in SENSITIVE_NAMES for part in path.parts):
        raise ValueError("write path may not name a sensitive file")
    return path.as_posix()


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _check_parent_chain(root: Path, relative: str) -> None:
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        if not _lexists(current):
            continue
        if current.is_symlink() or not current.is_dir():
            raise ValueError("write parent must be a real directory")


def _regular_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("replace target must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ValueError("replace target must be readable") from error


def _parse_new_manifest(content: str) -> Dict[str, object]:
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("new manifest must be valid JSON") from error
    return validate_manifest_data(data)


def _validate_manifest_ledger(
    root: Path, writes: Sequence[PlannedWrite], manifest: Mapping[str, object]
) -> None:
    records = {str(record["path"]): record for record in manifest["files"]}
    planned = {
        write.path: write
        for write in writes
        if write.path != MANIFEST_PATH and write.mode != "delete-owned"
    }
    for path, write in planned.items():
        record = records.get(path)
        if record is None or record.get("sha256") != _digest(
            write.content.encode("utf-8")
        ):
            raise ValueError("manifest hash must match every planned output")
    for path, record in records.items():
        if path in planned:
            continue
        _check_parent_chain(root, path)
        target = root / path
        if _digest(_regular_bytes(target)) != record["sha256"]:
            raise ValueError("manifest hash must match every retained output")


def preflight_outputs(
    root: Path,
    writes: Sequence[PlannedWrite],
    prior_manifest: Optional[Mapping[str, object]] = None,
) -> List[PlannedWrite]:
    """Validate the complete plan without creating directories or temporary files."""
    root = root.resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("output root must be a real directory")
    if not writes:
        raise ValueError("write plan must not be empty")
    normalized: List[PlannedWrite] = []
    seen = set()
    for write in writes:
        if not isinstance(write, PlannedWrite):
            raise ValueError("write plan contains an invalid item")
        path = _safe_relative_path(write.path)
        identity = path.casefold()
        if identity in seen:
            raise ValueError("write paths must be unique")
        seen.add(identity)
        if write.mode not in WRITE_MODES:
            raise ValueError("write mode must be create, replace-owned, or delete-owned")
        if write.mode == "delete-owned":
            if write.content is not None:
                raise ValueError("delete-owned content must be None")
        elif not isinstance(write.content, str):
            raise ValueError("write content must be text")
        normalized.append(
            PlannedWrite(path, write.content, write.mode, write.expected_sha256)
        )

    manifest_writes = [write for write in normalized if write.path == MANIFEST_PATH]
    if len(manifest_writes) != 1:
        raise ValueError("write plan requires exactly one manifest output")

    validated_prior = None
    prior_owned: Dict[str, str] = {}
    if prior_manifest is not None:
        validated_prior = validate_manifest_data(dict(prior_manifest))
        try:
            disk_prior = load_manifest(root / MANIFEST_PATH)
        except ValueError as error:
            raise ValueError("on-disk prior manifest is missing or invalid") from error
        if disk_prior != validated_prior:
            raise ValueError("on-disk prior manifest does not match supplied ownership")
        prior_owned = owned_file_hashes(validated_prior)

    for write in normalized:
        _check_parent_chain(root, write.path)
        target = root / write.path
        if write.mode == "create":
            if write.expected_sha256 is not None:
                raise ValueError("create mode cannot claim a prior SHA-256")
            if _lexists(target):
                if target.is_symlink():
                    raise ValueError("create target may not be a symbolic link")
                raise FileExistsError("refusing to overwrite unowned file '{}'".format(write.path))
            continue
        if validated_prior is None:
            raise ValueError("replace-owned requires a validated prior manifest")
        expected = write.expected_sha256
        if not isinstance(expected, str) or SHA256_PATTERN.fullmatch(expected) is None:
            raise ValueError("replace-owned requires an exact prior SHA-256")
        current = _regular_bytes(target)
        if _digest(current) != expected:
            raise ValueError("pre-update SHA-256 mismatch for '{}'".format(write.path))
        if write.path != MANIFEST_PATH and prior_owned.get(write.path) != expected:
            raise ValueError("prior manifest does not own '{}'".format(write.path))

    new_manifest = _parse_new_manifest(manifest_writes[0].content)
    new_paths = {str(record["path"]) for record in new_manifest["files"]}
    delete_paths = {
        write.path for write in normalized if write.mode == "delete-owned"
    }
    if delete_paths & new_paths:
        raise ValueError("delete-owned path may not remain in the new manifest")
    retired_paths = set(prior_owned) - new_paths
    if retired_paths != delete_paths:
        raise ValueError("every retired output requires one delete-owned plan entry")
    _validate_manifest_ledger(root, normalized, new_manifest)
    non_manifest = [write for write in normalized if write.path != MANIFEST_PATH]
    return non_manifest + manifest_writes


def _recheck_target(root: Path, write: PlannedWrite) -> None:
    _check_parent_chain(root, write.path)
    target = root / write.path
    if write.mode == "create":
        if _lexists(target):
            raise FileExistsError("create target appeared after preflight")
        return
    current = _regular_bytes(target)
    if _digest(current) != write.expected_sha256:
        raise ValueError("target changed after preflight")


def apply_outputs(
    root: Path,
    writes: Sequence[PlannedWrite],
    prior_manifest: Optional[Mapping[str, object]] = None,
) -> List[str]:
    """Stage every file, atomically replace each target, and install manifest last."""
    root = root.resolve()
    prepared = preflight_outputs(root, writes, prior_manifest=prior_manifest)
    staged: Dict[str, Path] = {}
    changed: List[str] = []
    try:
        for write in prepared:
            if write.mode == "delete-owned":
                continue
            target = root / write.path
            target.parent.mkdir(parents=True, exist_ok=True)
            _check_parent_chain(root, write.path)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".project-rules-bootstrap-", dir=str(target.parent)
            )
            temporary_path = Path(temporary)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(write.content.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
            staged[write.path] = temporary_path

        for write in prepared:
            _recheck_target(root, write)
            if write.mode == "delete-owned":
                (root / write.path).unlink()
            else:
                os.replace(str(staged[write.path]), str(root / write.path))
                staged.pop(write.path, None)
            changed.append(write.path)
        return changed
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
