"""Load, validate, and resolve the authoritative adapter registry."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple


REGISTRY_VERSION = "1.0"
REGISTRY_VERIFIED_AT = "2026-07-28"
ADAPTER_SUPPORT_LEVELS = frozenset(
    {"native-auto", "import-supported", "manual-reference", "unverified"}
)
SCOPE_LOADING_LEVELS = frozenset({"repository", "glob", "per-rule", "manual"})
IMPORT_CAPABILITIES = frozenset({"native", "import", "explicit-reference"})
SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".npmrc",
        ".pypirc",
        "id_rsa",
        "id_ed25519",
    }
)
REGISTRY_REQUIRED_FIELDS = (
    "id",
    "name",
    "path",
    "scope_loading",
    "import_capability",
    "support",
    "template",
    "verified_at",
    "sources",
)
REGISTRY_OPTIONAL_FIELDS = (
    "alternative_path",
    "shared_output",
    "selection_priority",
)
REGISTRY_ALLOWED_FIELDS = frozenset(REGISTRY_REQUIRED_FIELDS + REGISTRY_OPTIONAL_FIELDS)
MANIFEST_ADAPTER_FIELDS = (
    "id",
    "path",
    "support",
    "template",
    "registry_version",
    "scope_loading",
    "import_capability",
    "consumers",
)
_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:")
_SAFE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _registry_root(path: Path) -> Path:
    return path.parent.parent if path.parent.name == "references" else path.parent


def _is_sensitive_part(part: str) -> bool:
    lowered = part.lower()
    return lowered in SENSITIVE_NAMES or lowered.startswith(".env.")


def validate_relative_path(value: object, *, allow_patterns: bool, field: str) -> str:
    """Return a safe portable relative path or raise ``ValueError``."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(field))
    path = value.strip()
    if (
        path.startswith(("/", "\\"))
        or _DRIVE_PATH_PATTERN.match(path)
        or "\\" in path
        or ":" in path
    ):
        raise ValueError("{} must be a portable relative path".format(field))
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("{} must not contain empty, current, or parent segments".format(field))
    if any(_is_sensitive_part(part) for part in parts):
        raise ValueError("{} must not name a sensitive path".format(field))
    pattern_text = path.replace("<rule>", "") if allow_patterns else path
    if not allow_patterns and "<rule>" in path:
        raise ValueError("{} must not contain placeholders".format(field))
    if any(character in pattern_text for character in ("?", "[", "]")):
        raise ValueError("{} contains an unsupported path pattern".format(field))
    if not allow_patterns and "*" in pattern_text:
        raise ValueError("{} must not contain wildcards".format(field))
    if allow_patterns:
        for part in parts[:-1]:
            if "*" in part:
                raise ValueError("{} may use '*' only in the final segment".format(field))
        if path.count("<rule>") > 1:
            raise ValueError("{} may contain at most one <rule> placeholder".format(field))
    return path


def safe_target_path(root: Path, relative_path: str) -> Path:
    """Resolve an exact target path without allowing symlinks or root escape."""
    safe_relative = validate_relative_path(
        relative_path, allow_patterns=False, field="adapter target path"
    )
    resolved_root = root.resolve(strict=False)
    target = resolved_root.joinpath(*safe_relative.split("/"))
    try:
        target.resolve(strict=False).relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError("adapter target path resolves outside the target root") from error

    current = resolved_root
    for part in safe_relative.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError("adapter target path contains a symlink")
    return target


def _validate_https_sources(value: object) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError("Every adapter registry entry requires non-empty HTTPS sources")
    if not all(isinstance(source, str) and source.startswith("https://") for source in value):
        raise ValueError("Every adapter registry entry requires non-empty HTTPS sources")


def _validate_verified_date(value: object) -> None:
    if value != REGISTRY_VERIFIED_AT:
        raise ValueError(
            "Every adapter registry entry requires verified_at {}".format(REGISTRY_VERIFIED_AT)
        )
    try:
        date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError("Adapter registry verified_at must be an ISO date") from error


def _validate_template(template_root: Path, template_value: object) -> None:
    template = validate_relative_path(
        template_value, allow_patterns=False, field="adapter template"
    )
    resolved_root = template_root.resolve(strict=False)
    target = resolved_root.joinpath(*template.split("/"))
    try:
        target.resolve(strict=False).relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError("Adapter template resolves outside the registry root") from error
    current = resolved_root
    for part in template.split("/"):
        current = current / part
        if current.is_symlink():
            raise ValueError("Adapter template must not contain a symlink")
    if not target.is_file():
        raise ValueError("Every adapter registry entry names an existing template")


def validate_adapter_registry_data(
    data: object, template_root: Optional[Path] = None
) -> Dict[str, object]:
    """Validate registry structure, identities, output paths, and shared outputs."""
    if not isinstance(data, dict):
        raise ValueError("Adapter registry must be an object")
    if set(data) != {"version", "adapters"}:
        raise ValueError("Adapter registry allows only version and adapters")
    if data.get("version") != REGISTRY_VERSION:
        raise ValueError("Adapter registry version must be {}".format(REGISTRY_VERSION))
    adapters = data.get("adapters")
    if not isinstance(adapters, list):
        raise ValueError("Adapter registry adapters must be an array")

    seen_ids = set()
    by_path: Dict[str, List[Dict[str, object]]] = {}
    for adapter in adapters:
        if not isinstance(adapter, dict):
            raise ValueError("Every adapter registry entry must be an object")
        unknown_fields = set(adapter) - REGISTRY_ALLOWED_FIELDS
        if unknown_fields:
            raise ValueError(
                "Adapter registry entry has unsupported fields: {}".format(
                    ", ".join(sorted(unknown_fields))
                )
            )
        for key in REGISTRY_REQUIRED_FIELDS:
            if key == "sources":
                continue
            if not isinstance(adapter.get(key), str) or not str(adapter[key]).strip():
                raise ValueError(
                    "Every adapter registry entry requires a non-empty {}".format(key)
                )
        adapter_id = str(adapter["id"])
        if not _SAFE_ID_PATTERN.fullmatch(adapter_id):
            raise ValueError("Adapter registry id must use lowercase letters, digits, and hyphens")
        if adapter_id in seen_ids:
            raise ValueError("Adapter registry IDs must be unique")
        seen_ids.add(adapter_id)
        if "support_level" in adapter:
            raise ValueError("Adapter registry support_level alias is not allowed; use support only")
        if adapter["support"] not in ADAPTER_SUPPORT_LEVELS:
            raise ValueError("Every adapter registry entry requires a supported support value")
        if adapter["scope_loading"] not in SCOPE_LOADING_LEVELS:
            raise ValueError("Every adapter registry entry requires a supported scope_loading")
        if adapter["import_capability"] not in IMPORT_CAPABILITIES:
            raise ValueError("Every adapter registry entry requires a supported import_capability")
        _validate_verified_date(adapter["verified_at"])
        _validate_https_sources(adapter["sources"])
        output_path = validate_relative_path(
            adapter["path"], allow_patterns=True, field="adapter output path"
        )
        if "alternative_path" in adapter:
            validate_relative_path(
                adapter["alternative_path"],
                allow_patterns=True,
                field="adapter alternative path",
            )
        if template_root is not None:
            _validate_template(template_root, adapter["template"])
        else:
            validate_relative_path(
                adapter["template"], allow_patterns=False, field="adapter template"
            )
        shared_output = adapter.get("shared_output")
        priority = adapter.get("selection_priority")
        if shared_output is not None:
            if not isinstance(shared_output, str) or not _SAFE_ID_PATTERN.fullmatch(shared_output):
                raise ValueError("shared_output must be a non-empty lowercase identifier")
            if not isinstance(priority, int) or isinstance(priority, bool):
                raise ValueError("shared output entries require integer selection_priority")
        elif priority is not None:
            raise ValueError("selection_priority requires shared_output")
        by_path.setdefault(output_path, []).append(adapter)

    for output_path, entries in by_path.items():
        if len(entries) < 2:
            continue
        groups = {entry.get("shared_output") for entry in entries}
        if len(groups) != 1 or None in groups:
            raise ValueError(
                "Adapter output '{}' is duplicated without one shared_output contract".format(
                    output_path
                )
            )
        comparable = ("path", "template", "support", "scope_loading", "import_capability")
        signatures = {tuple(entry[field] for field in comparable) for entry in entries}
        if len(signatures) != 1:
            raise ValueError("Shared adapter outputs must use identical output metadata")
        priorities = [entry["selection_priority"] for entry in entries]
        if len(priorities) != len(set(priorities)):
            raise ValueError("Shared adapter output priorities must be unique")
    return data


def load_adapter_registry(path: Path) -> Dict[str, object]:
    """Load and validate one authoritative registry JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Adapter registry is not valid JSON: {}".format(error)) from error
    return validate_adapter_registry_data(data, _registry_root(path))


def adapter_registry_records(
    registry: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    records: Dict[str, Dict[str, object]] = {}
    for adapter in registry.get("adapters", []):
        if isinstance(adapter, dict):
            records[str(adapter["id"])] = adapter
    return records


def resolve_adapter_selection(
    registry: Dict[str, object], selected_ids: Iterable[str]
) -> Tuple[List[Dict[str, object]], List[str]]:
    """Resolve selected assistants to one unambiguous output owner per path."""
    validate_adapter_registry_data(registry)
    records = adapter_registry_records(registry)
    selected = sorted(set(str(adapter_id) for adapter_id in selected_ids))
    unverified: List[str] = []
    groups: Dict[str, List[Dict[str, object]]] = {}
    for adapter_id in selected:
        adapter = records.get(adapter_id)
        if adapter is None or adapter["support"] == "unverified":
            unverified.append(adapter_id)
            continue
        group = str(adapter.get("shared_output", adapter_id))
        groups.setdefault(group, []).append(adapter)

    resolved: List[Dict[str, object]] = []
    for entries in groups.values():
        owner = max(entries, key=lambda entry: int(entry.get("selection_priority", 0)))
        consumers = sorted(str(entry["id"]) for entry in entries)
        resolved.append(
            {
                "id": owner["id"],
                "path": owner["path"],
                "support": owner["support"],
                "template": owner["template"],
                "registry_version": registry["version"],
                "scope_loading": owner["scope_loading"],
                "import_capability": owner["import_capability"],
                "consumers": consumers,
            }
        )
    return (
        sorted(resolved, key=lambda adapter: (str(adapter["path"]), str(adapter["id"]))),
        unverified,
    )


def expand_registry_pattern(pattern: str) -> str:
    """Return a safe ``Path.glob`` pattern for a validated registry path."""
    return pattern.replace("<rule>", "*")
