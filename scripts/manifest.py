"""Validate the small v2 ownership and confirmation manifest."""

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Dict, Mapping


MANIFEST_VERSION = "2.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TOP_LEVEL_FIELDS = {"version", "project", "source", "files", "confirmations"}
PROJECT_FIELDS = {"name", "language"}
SOURCE_FIELDS = {"kind", "revision", "paths"}
FILE_FIELDS = {"path", "sha256", "kind", "adapter_id"}
CONFIRMATION_FIELDS = {
    "id",
    "rule_id",
    "scope",
    "text_sha256",
    "reason",
    "exception_policy",
    "verification",
    "recorded_at",
}
SENSITIVE_NAMES = {
    ".env",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets",
    "secrets.json",
}
UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _require_object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError("{} must be an object".format(label))
    return value


def _require_exact_fields(
    value: Mapping[str, object], required: set, allowed: set, label: str
) -> None:
    unexpected = set(value) - allowed
    if unexpected:
        if label == "manifest":
            raise ValueError(
                "unexpected manifest field: {}".format(sorted(unexpected)[0])
            )
        raise ValueError("unexpected {} field: {}".format(label, sorted(unexpected)[0]))
    missing = required - set(value)
    if missing:
        raise ValueError("{} is missing field: {}".format(label, sorted(missing)[0]))


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be non-empty text".format(label))
    return value.strip()


def _safe_relative_path(value: object, label: str) -> str:
    path = _require_text(value, label)
    if "\\" in path or "\x00" in path or ":" in path:
        raise ValueError("{} must use a safe relative POSIX path".format(label))
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith("/") or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise ValueError("{} must use a safe relative POSIX path".format(label))
    if any(part.lower() in SENSITIVE_NAMES for part in pure.parts):
        raise ValueError("{} may not name a sensitive file".format(label))
    return pure.as_posix()


def _validate_project(value: object) -> None:
    project = _require_object(value, "project")
    _require_exact_fields(project, PROJECT_FIELDS, PROJECT_FIELDS, "project")
    _require_text(project["name"], "project.name")
    if project["language"] not in {"en", "zh-CN"}:
        raise ValueError("project.language must be en or zh-CN")


def _validate_source(value: object) -> None:
    source = _require_object(value, "source")
    _require_exact_fields(source, SOURCE_FIELDS, SOURCE_FIELDS, "source")
    if source["kind"] not in {"git", "full-scan", "bounded-scan"}:
        raise ValueError("source.kind is invalid")
    revision = source["revision"]
    if revision is not None:
        _require_text(revision, "source.revision")
    paths = source["paths"]
    if not isinstance(paths, list) or not paths:
        raise ValueError("source.paths must be a non-empty list")
    for path in paths:
        if path != ".":
            _safe_relative_path(path, "source path")


def _validate_files(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("files must be a list")
    seen = set()
    for index, item in enumerate(value):
        record = _require_object(item, "files[{}]".format(index))
        kind = record.get("kind")
        required = {"path", "sha256", "kind"}
        if kind == "adapter":
            required.add("adapter_id")
        _require_exact_fields(record, required, FILE_FIELDS, "file record")
        path = _safe_relative_path(record["path"], "file path")
        if path in seen:
            raise ValueError("file paths must be unique")
        seen.add(path)
        sha256 = record["sha256"]
        if not isinstance(sha256, str) or SHA256_PATTERN.fullmatch(sha256) is None:
            raise ValueError("file sha256 must be lowercase hexadecimal")
        if kind not in {"canonical", "adapter", "manifest"}:
            raise ValueError("file kind is invalid")
        if kind != "adapter" and "adapter_id" in record:
            raise ValueError("adapter_id is valid only for adapter files")
        if kind == "adapter":
            adapter_id = _require_text(record["adapter_id"], "adapter_id")
            if SAFE_ID_PATTERN.fullmatch(adapter_id) is None:
                raise ValueError("adapter_id is invalid")


def _validate_confirmations(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("confirmations must be a list")
    seen_ids = set()
    seen_rules = set()
    for index, item in enumerate(value):
        record = _require_object(item, "confirmations[{}]".format(index))
        _require_exact_fields(
            record,
            CONFIRMATION_FIELDS,
            CONFIRMATION_FIELDS,
            "confirmation record",
        )
        confirmation_id = _require_text(record["id"], "confirmation id")
        rule_id = _require_text(record["rule_id"], "confirmation rule_id")
        if SAFE_ID_PATTERN.fullmatch(confirmation_id) is None:
            raise ValueError("confirmation id is invalid")
        if SAFE_ID_PATTERN.fullmatch(rule_id) is None:
            raise ValueError("confirmation rule_id is invalid")
        if confirmation_id in seen_ids or rule_id in seen_rules:
            raise ValueError("confirmation ids and rule ids must be unique")
        seen_ids.add(confirmation_id)
        seen_rules.add(rule_id)
        for field in (
            "scope",
            "reason",
            "exception_policy",
            "verification",
        ):
            _require_text(record[field], "confirmation.{}".format(field))
        recorded_at = _require_text(
            record["recorded_at"], "confirmation.recorded_at"
        )
        if UTC_TIMESTAMP_PATTERN.fullmatch(recorded_at) is None:
            raise ValueError("confirmation.recorded_at must be ISO-8601 UTC")
        try:
            datetime.strptime(recorded_at, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ValueError("confirmation.recorded_at must be ISO-8601 UTC") from error
        text_sha256 = record["text_sha256"]
        if not isinstance(text_sha256, str) or SHA256_PATTERN.fullmatch(text_sha256) is None:
            raise ValueError("confirmation.text_sha256 must be lowercase hexadecimal")


def validate_manifest_data(data: object) -> Dict[str, object]:
    """Return a validated defensive copy of a v2 manifest."""
    manifest = _require_object(data, "manifest")
    _require_exact_fields(manifest, TOP_LEVEL_FIELDS, TOP_LEVEL_FIELDS, "manifest")
    if manifest["version"] != MANIFEST_VERSION:
        raise ValueError("manifest.version must be {}".format(MANIFEST_VERSION))
    _validate_project(manifest["project"])
    _validate_source(manifest["source"])
    _validate_files(manifest["files"])
    _validate_confirmations(manifest["confirmations"])
    return deepcopy(dict(manifest))


def load_manifest(path: Path) -> Dict[str, object]:
    """Load one UTF-8 JSON manifest and validate its complete shape."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("manifest must be readable UTF-8 JSON") from error
    return validate_manifest_data(data)


def owned_file_hashes(manifest: Mapping[str, object]) -> Dict[str, str]:
    """Return the exact owned path-to-hash map from a validated manifest."""
    validated = validate_manifest_data(dict(manifest))
    return {
        str(record["path"]): str(record["sha256"])
        for record in validated["files"]
    }


def confirmed_constraints(manifest: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    """Return prior explicit confirmations keyed by canonical rule ID."""
    validated = validate_manifest_data(dict(manifest))
    return {
        str(record["rule_id"]): dict(record)
        for record in validated["confirmations"]
    }
