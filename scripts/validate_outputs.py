"""Validate generated canonical rules and tool adapters without changing them."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union


MANIFEST_PATH = Path(".ai/rules-manifest.json")
CANONICAL_RULES_PATH = Path(".ai/rules")
SCOPE_HEADING = "适用范围"
CONFIRMED_CONSTRAINTS_HEADING = "已确认的强约束"
CANONICAL_HEADING_TRANSLATIONS = {
    SCOPE_HEADING: "Scope",
    CONFIRMED_CONSTRAINTS_HEADING: "Confirmed constraints",
}
RULE_ID_PATTERN = re.compile(r"<!--\s*rule-id:\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*-->")
ADAPTER_SYNTAX_PATTERN = re.compile(
    r"^(?:alwaysApply|globs|applyTo|fileMatchPattern)\s*:", re.MULTILINE
)
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<body>.*?)\n---(?:\s*\n|\Z)", re.DOTALL)
FRONTMATTER_FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(\S.*?)\s*$")
ADAPTER_METADATA_PATTERN = re.compile(
    r"<!--\s*(adapter-id|adapter|tool-id|adapter-support|support|support-level)"
    r"\s*:\s*([^\s]+)\s*-->",
    re.IGNORECASE,
)
KNOWN_ADAPTER_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "RULES.md",
    ".cursor/rules/**/*.mdc",
    ".trae/rules/**/*.md",
    ".codebuddy/rules/**/*.mdc",
)
BUNDLED_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "references" / "adapters.json"
ADAPTER_SUPPORT_LEVELS = frozenset(
    {"native-auto", "import-supported", "manual-reference", "unverified"}
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
REGISTRY_VERIFIED_AT = "2026-07-28"
RegistryInput = Optional[Union[Path, Dict[str, object]]]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def load_manifest(path: Path) -> Dict[str, object]:
    """Load a rules Manifest and reject malformed JSON or unsupported shapes."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Manifest is not valid JSON: {}".format(error)) from error
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError("Manifest must be an object with a rules array")
    baseline = data.get("scan_baseline")
    if not isinstance(baseline, dict):
        raise ValueError("Final Manifest requires an initialized scan_baseline object")
    if baseline.get("kind") not in {"git", "full-scan"}:
        raise ValueError("Final Manifest scan_baseline requires kind git or full-scan")
    if not isinstance(baseline.get("captured_at"), str) or not baseline["captured_at"].strip():
        raise ValueError("Final Manifest scan_baseline requires captured_at")
    if not isinstance(baseline.get("paths"), list):
        raise ValueError("Final Manifest scan_baseline requires a paths array")
    for rule in data["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("Every Manifest rule must be an object")
        for key in ("id", "type", "status"):
            if not isinstance(rule.get(key), str) or not rule[key].strip():
                raise ValueError("Every Manifest rule requires a non-empty {}".format(key))
    adapters = data.get("adapters", [])
    if not isinstance(adapters, list):
        raise ValueError("Manifest adapters must be an array when present")
    for adapter in adapters:
        if not isinstance(adapter, dict):
            raise ValueError("Every Manifest adapter must be an object")
        for key in ("id", "path"):
            if not isinstance(adapter.get(key), str) or not adapter[key].strip():
                raise ValueError("Every Manifest adapter requires a non-empty {}".format(key))
        if _adapter_support(adapter) is None:
            raise ValueError("Every Manifest adapter requires a non-empty support")
    return data


def _registry_root(path: Path) -> Path:
    """Return the repository root for a conventional references/adapters.json path."""
    return path.parent.parent if path.parent.name == "references" else path.parent


def _validate_adapter_registry(
    data: object, template_root: Optional[Path] = None
) -> Dict[str, object]:
    if not isinstance(data, dict) or not isinstance(data.get("adapters"), list):
        raise ValueError("Adapter registry must be an object with an adapters array")
    for adapter in data["adapters"]:
        if not isinstance(adapter, dict):
            raise ValueError("Every adapter registry entry must be an object")
        for key in REGISTRY_REQUIRED_FIELDS:
            if key == "sources":
                continue
            if not isinstance(adapter.get(key), str) or not adapter[key].strip():
                raise ValueError("Every adapter registry entry requires a non-empty {}".format(key))
        support = adapter["support"]
        if "support_level" in adapter:
            raise ValueError("Adapter registry support_level alias is not allowed; use support only")
        if support not in ADAPTER_SUPPORT_LEVELS:
            raise ValueError("Every adapter registry entry requires a supported support value")
        if adapter["verified_at"] != REGISTRY_VERIFIED_AT:
            raise ValueError("Every adapter registry entry requires verified_at {}".format(REGISTRY_VERIFIED_AT))
        sources = adapter["sources"]
        if not isinstance(sources, list) or not sources or not all(
            isinstance(source, str) and source.startswith("https://") for source in sources
        ):
            raise ValueError("Every adapter registry entry requires non-empty HTTPS sources")
        template = Path(adapter["template"])
        if template_root is not None:
            template = template_root / template
        if not template.is_file():
            raise ValueError("Every adapter registry entry names an existing template")
    return data


def load_adapter_registry(path: Path) -> Dict[str, object]:
    """Load the authoritative adapter registry from JSON."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Adapter registry is not valid JSON: {}".format(error)) from error
    return _validate_adapter_registry(data, _registry_root(path))


def _resolve_adapter_registry(registry: RegistryInput) -> Optional[Dict[str, object]]:
    if registry is None:
        if not BUNDLED_REGISTRY_PATH.is_file():
            return None
        return load_adapter_registry(BUNDLED_REGISTRY_PATH)
    if isinstance(registry, Path):
        return load_adapter_registry(registry)
    if isinstance(registry, dict):
        return _validate_adapter_registry(registry)
    raise ValueError("Adapter registry must be a path or object")


def _rule_records(manifest: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    return {str(rule["id"]): rule for rule in manifest.get("rules", []) if isinstance(rule, dict)}


def _has_heading(content: str, heading: str) -> bool:
    english = CANONICAL_HEADING_TRANSLATIONS.get(heading)
    suffix = r"(?:\s*/\s+{})?".format(re.escape(english)) if english else ""
    return re.search(r"^##\s+{}{}\s*$".format(re.escape(heading), suffix), content, re.MULTILINE) is not None


def _adapter_support(adapter: Dict[str, object]) -> Optional[str]:
    for key in ("support", "support_level"):
        value = adapter.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def validate_rule_file(path: Path, manifest: Dict[str, object]) -> List[ValidationIssue]:
    """Validate required headings and explicit constraint IDs in one canonical rule file."""
    issue_path = path.as_posix()
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [ValidationIssue("unreadable-rule-file", issue_path, "Cannot read rule file: {}".format(error))]

    issues: List[ValidationIssue] = []
    if not _has_heading(content, SCOPE_HEADING):
        issues.append(
            ValidationIssue("missing-scope", issue_path, "Canonical rule file is missing '## {}'".format(SCOPE_HEADING))
        )
    if ADAPTER_SYNTAX_PATTERN.search(content):
        issues.append(
            ValidationIssue(
                "adapter-syntax-in-canonical-rule",
                issue_path,
                "Canonical rule file contains adapter-only frontmatter syntax",
            )
        )

    if path.name == "restrictions.md" and _has_heading(content, CONFIRMED_CONSTRAINTS_HEADING):
        rules = _rule_records(manifest)
        for rule_id in RULE_ID_PATTERN.findall(content):
            rule = rules.get(rule_id)
            is_confirmed_constraint = (
                rule is not None
                and rule.get("type") == "constraint"
                and rule.get("status") == "confirmed"
            )
            if not is_confirmed_constraint:
                issues.append(
                    ValidationIssue(
                        "unconfirmed-constraint",
                        issue_path,
                        "Constraint '{}' is not confirmed in the Manifest".format(rule_id),
                    )
                )
    return issues


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _canonical_rule_files(root: Path) -> List[Path]:
    canonical_root = root / CANONICAL_RULES_PATH
    if not canonical_root.is_dir():
        return []
    return sorted(path for path in canonical_root.rglob("*.md") if path.is_file())


def _adapter_paths(root: Path, manifest: Dict[str, object]) -> List[Path]:
    patterns = set(KNOWN_ADAPTER_PATHS)
    for adapter in manifest.get("adapters", []):
        if isinstance(adapter, dict) and isinstance(adapter.get("path"), str):
            patterns.add(str(adapter["path"]))
    paths = set()
    for pattern in sorted(patterns):
        paths.update(path for path in root.glob(pattern) if path.is_file())
    return sorted(paths, key=lambda path: _relative_path(root, path))


def _adapter_metadata(content: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    frontmatter = FRONTMATTER_PATTERN.match(content)
    if frontmatter is not None:
        for line in frontmatter.group("body").splitlines():
            field = FRONTMATTER_FIELD_PATTERN.match(line)
            if field is not None:
                key, value = field.groups()
                if key in {"adapter-id", "adapter", "tool-id", "adapter-support", "support", "support-level"}:
                    metadata[key] = value
    for key, value in ADAPTER_METADATA_PATTERN.findall(content):
        metadata[key.lower()] = value
    return metadata


def _adapter_registry_records(registry: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    records: Dict[str, Dict[str, object]] = {}
    for adapter in registry.get("adapters", []):
        if isinstance(adapter, dict):
            records[str(adapter["id"])] = adapter
    return records


def _manifest_adapter_issues(
    manifest: Dict[str, object], registry: Dict[str, object]
) -> List[ValidationIssue]:
    expected_adapters = _adapter_registry_records(registry)
    issues: List[ValidationIssue] = []
    for adapter in manifest.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        adapter_id = str(adapter["id"])
        expected = expected_adapters.get(adapter_id)
        expected_support = _adapter_support(expected) if expected is not None else None
        claimed_support = _adapter_support(adapter)
        if expected_support is None or claimed_support != expected_support:
            expected_text = expected_support if expected_support is not None else "no registered support level"
            issues.append(
                ValidationIssue(
                    "adapter-support-mismatch",
                    MANIFEST_PATH.as_posix(),
                    "Manifest adapter '{}' claims '{}' but the registry requires '{}'".format(
                        adapter_id, claimed_support, expected_text
                    ),
                )
            )
    return issues


def _adapter_issues(
    root: Path,
    manifest: Dict[str, object],
    registry: Optional[Dict[str, object]],
    canonical_files: List[Path],
) -> List[ValidationIssue]:
    registry_records = _adapter_registry_records(registry) if registry is not None else {}
    canonical_bodies = []
    for path in canonical_files:
        try:
            body = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if len(body) >= 80:
            canonical_bodies.append((_relative_path(root, path), body))

    issues: List[ValidationIssue] = []
    for path in _adapter_paths(root, manifest):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        issue_path = _relative_path(root, path)
        metadata = _adapter_metadata(content)
        adapter_id = metadata.get("adapter-id") or metadata.get("adapter") or metadata.get("tool-id")
        claimed_support = (
            metadata.get("adapter-support")
            or metadata.get("support")
            or metadata.get("support-level")
        )
        expected = registry_records.get(adapter_id) if adapter_id else None
        expected_support = _adapter_support(expected) if expected is not None else None
        if claimed_support is not None and expected_support is not None and claimed_support != expected_support:
            issues.append(
                ValidationIssue(
                    "adapter-support-mismatch",
                    issue_path,
                    "Adapter '{}' claims '{}' but the registry requires '{}'".format(
                        adapter_id, claimed_support, expected_support
                    ),
                )
            )
        for canonical_path, canonical_body in canonical_bodies:
            if canonical_body in content:
                issues.append(
                    ValidationIssue(
                        "adapter-content-duplication",
                        issue_path,
                        "Adapter copies the complete canonical rule body from '{}'".format(canonical_path),
                    )
                )
    return issues


def validate_output_tree(root: Path, registry: RegistryInput = None) -> List[ValidationIssue]:
    """Return deterministic validation issues for a generated output tree."""
    root = root.resolve(strict=False)
    manifest_path = root / MANIFEST_PATH
    issues: List[ValidationIssue] = []
    try:
        manifest = load_manifest(manifest_path)
    except ValueError as error:
        code = "missing-manifest" if not manifest_path.exists() else "invalid-manifest"
        issues.append(ValidationIssue(code, MANIFEST_PATH.as_posix(), str(error)))
        manifest = {"rules": []}

    try:
        adapter_registry = _resolve_adapter_registry(registry)
    except ValueError as error:
        issues.append(ValidationIssue("invalid-adapter-registry", "references/adapters.json", str(error)))
        adapter_registry = None

    canonical_files = _canonical_rule_files(root)
    if not canonical_files:
        issues.append(
            ValidationIssue(
                "missing-canonical-rules",
                CANONICAL_RULES_PATH.as_posix(),
                "Generated output must contain at least one canonical rule file",
            )
        )
    seen_rule_ids: Dict[str, str] = {}
    for path in canonical_files:
        for issue in validate_rule_file(path, manifest):
            issues.append(ValidationIssue(issue.code, _relative_path(root, path), issue.message))
        content = path.read_text(encoding="utf-8")
        for rule_id in RULE_ID_PATTERN.findall(content):
            first_path = seen_rule_ids.get(rule_id)
            current_path = _relative_path(root, path)
            if first_path is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate-rule-id",
                        current_path,
                        "Rule ID '{}' is already defined in '{}'".format(rule_id, first_path),
                    )
                )
            else:
                seen_rule_ids[rule_id] = current_path
    if adapter_registry is not None:
        issues.extend(_manifest_adapter_issues(manifest, adapter_registry))
    issues.extend(_adapter_issues(root, manifest, adapter_registry, canonical_files))
    return sorted(issues, key=lambda issue: (issue.path, issue.code, issue.message))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--registry", type=Path, help="authoritative adapters.json path")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    issues = validate_output_tree(args.root, args.registry)
    for issue in issues:
        print("{}: {}: {}".format(issue.path, issue.code, issue.message))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
