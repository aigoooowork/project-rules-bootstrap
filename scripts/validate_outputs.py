"""Validate generated canonical rules and tool adapters without changing them."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple, Union

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.adapter_registry import (
    ADAPTER_SUPPORT_LEVELS,
    MANIFEST_ADAPTER_FIELDS,
    REGISTRY_VERSION,
    adapter_registry_records,
    expand_registry_pattern,
    load_adapter_registry,
    resolve_adapter_selection,
    safe_target_path,
    validate_adapter_registry_data,
    validate_relative_path,
)


MANIFEST_PATH = Path(".ai/rules-manifest.json")
CANONICAL_RULES_PATH = Path(".ai/rules")
BUNDLED_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "references" / "adapters.json"
LANGUAGE_HEADINGS = {
    "en": {
        "scope": "Scope",
        "facts": "Confirmed facts",
        "constraints": "Confirmed constraints",
        "rules": "Execution rules",
        "verification": "Verification",
        "related": "Related rules",
    },
    "zh-CN": {
        "scope": "适用范围",
        "facts": "已确认事实",
        "constraints": "已确认的强约束",
        "rules": "执行规则",
        "verification": "验证方式",
        "related": "相关规则",
    },
}
DOMAIN_VALUES = frozenset(
    {
        "project",
        "architecture",
        "coding-style",
        "frontend",
        "backend",
        "api",
        "database",
        "testing",
        "security",
        "restrictions",
    }
)
RULE_TYPE_VALUES = frozenset({"fact", "convention", "constraint"})
RULE_STATUS_VALUES = frozenset({"confirmed", "candidate", "unknown", "conflict", "stale"})
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
EVIDENCE_KIND_VALUES = frozenset(
    {"source", "configuration", "documentation", "git", "user-confirmation"}
)
CONFIRMATION_DECISIONS = frozenset({"confirmed", "rejected", "deferred"})
RULE_ID_PATTERN = re.compile(r"<!--\s*rule-id:\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*-->")
RULE_ID_VALUE_PATTERN = re.compile(
    r"^(project|architecture|coding-style|frontend|backend|api|database|testing|security|restrictions)"
    r"(\.[a-z0-9][a-z0-9._-]*)+$"
)
ADAPTER_SYNTAX_PATTERN = re.compile(
    r"^(?:alwaysApply|globs|applyTo|fileMatchPattern)\s*:", re.MULTILINE
)
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<body>.*?)\n---(?:\s*\n|\Z)", re.DOTALL)
FRONTMATTER_FIELD_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(\S.*?)\s*$")
ADAPTER_METADATA_PATTERN = re.compile(
    r"<!--\s*(adapter-id|adapter|tool-id|adapter-support|support|support-level|"
    r"adapter-scope|adapter-loading|adapter-consumers)\s*:\s*([^\r\n]+?)\s*-->",
    re.IGNORECASE,
)
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TOP_LEVEL_LIST_ITEM_PATTERN = re.compile(r"^[-*+]\s+\S")
RegistryInput = Optional[Union[Path, Dict[str, object]]]


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def _require_object(
    value: object,
    *,
    label: str,
    required: Iterable[str],
    allowed: Iterable[str],
) -> Dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("{} must be an object".format(label))
    required_set = set(required)
    allowed_set = set(allowed)
    missing = required_set - set(value)
    if missing:
        raise ValueError(
            "{} requires {}".format(label, ", ".join(sorted(missing)))
        )
    additional = set(value) - allowed_set
    if additional:
        raise ValueError(
            "{} has unsupported properties: {}".format(
                label, ", ".join(sorted(additional))
            )
        )
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(label))
    return value.strip()


def _require_datetime(value: object, label: str) -> str:
    text = _require_string(value, label)
    if "T" not in text:
        raise ValueError("{} must be an ISO-8601 date-time".format(label))
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as error:
        raise ValueError("{} must be an ISO-8601 date-time".format(label)) from error
    if parsed.tzinfo is None:
        raise ValueError("{} must include a timezone".format(label))
    return text


def _require_string_array(
    value: object, label: str, *, min_items: int = 0, unique: bool = False
) -> List[str]:
    if not isinstance(value, list):
        raise ValueError("{} must be an array".format(label))
    values = [_require_string(item, "{} item".format(label)) for item in value]
    if len(values) < min_items:
        raise ValueError("{} requires at least {} item(s)".format(label, min_items))
    if unique and len(values) != len(set(values)):
        raise ValueError("{} items must be unique".format(label))
    return values


def _validate_evidence(value: object, rule_id: str, index: int) -> Dict[str, object]:
    label = "Rule '{}' evidence {}".format(rule_id, index)
    record = _require_object(
        value,
        label=label,
        required=("kind", "location", "observation", "captured_at"),
        allowed=(
            "kind",
            "location",
            "observation",
            "captured_at",
            "start_line",
            "end_line",
            "commit",
        ),
    )
    if record["kind"] not in EVIDENCE_KIND_VALUES:
        raise ValueError("{} kind is unsupported".format(label))
    _require_string(record["location"], "{} location".format(label))
    _require_string(record["observation"], "{} observation".format(label))
    _require_datetime(record["captured_at"], "{} captured_at".format(label))
    for field in ("start_line", "end_line"):
        if field in record and (
            not isinstance(record[field], int)
            or isinstance(record[field], bool)
            or int(record[field]) < 1
        ):
            raise ValueError("{} {} must be a positive integer".format(label, field))
    if (
        "start_line" in record
        and "end_line" in record
        and int(record["end_line"]) < int(record["start_line"])
    ):
        raise ValueError("{} end_line must not precede start_line".format(label))
    if "commit" in record:
        _require_string(record["commit"], "{} commit".format(label))
    return record


def _validate_rule(value: object, index: int) -> Dict[str, object]:
    label = "Manifest rule {}".format(index)
    record = _require_object(
        value,
        label=label,
        required=("id", "domain", "type", "status", "scope", "text", "confidence", "evidence"),
        allowed=(
            "id",
            "domain",
            "type",
            "status",
            "scope",
            "text",
            "confidence",
            "evidence",
            "confirmation_id",
            "reason",
            "exception_policy",
            "verification",
            "stale",
            "supersedes",
        ),
    )
    rule_id = _require_string(record["id"], "{} id".format(label))
    if not RULE_ID_VALUE_PATTERN.fullmatch(rule_id):
        raise ValueError("{} id has an unsupported format".format(label))
    if record["domain"] not in DOMAIN_VALUES:
        raise ValueError("{} domain is unsupported".format(label))
    if not rule_id.startswith(str(record["domain"]) + "."):
        raise ValueError("{} id must start with its domain".format(label))
    if record["type"] not in RULE_TYPE_VALUES:
        raise ValueError("{} type is unsupported".format(label))
    if record["status"] not in RULE_STATUS_VALUES:
        raise ValueError("{} status is unsupported".format(label))
    _require_string(record["scope"], "{} scope".format(label))
    _require_string(record["text"], "{} text".format(label))
    if record["confidence"] not in CONFIDENCE_VALUES:
        raise ValueError("{} confidence is unsupported".format(label))
    evidence = record["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("{} evidence requires at least one item".format(label))
    for evidence_index, item in enumerate(evidence):
        _validate_evidence(item, rule_id, evidence_index)
    if record["type"] == "constraint":
        for field in (
            "confirmation_id",
            "reason",
            "exception_policy",
            "verification",
        ):
            _require_string(record.get(field), "{} {}".format(label, field))
    else:
        forbidden = {"confirmation_id", "reason", "exception_policy"} & set(record)
        if forbidden:
            raise ValueError(
                "{} non-constraint cannot contain {}".format(
                    label, ", ".join(sorted(forbidden))
                )
            )
        if "verification" in record:
            _require_string(record["verification"], "{} verification".format(label))
    stale = record.get("stale")
    if stale is not None and not isinstance(stale, bool):
        raise ValueError("{} stale must be boolean".format(label))
    if record["status"] == "stale" and stale is not True:
        raise ValueError("{} stale status requires stale true".format(label))
    if stale is True and record["status"] != "stale":
        raise ValueError("{} stale true requires stale status".format(label))
    if "supersedes" in record:
        _require_string(record["supersedes"], "{} supersedes".format(label))
    return record


def _validate_confirmation(value: object, index: int) -> Dict[str, object]:
    label = "Manifest confirmation {}".format(index)
    record = _require_object(
        value,
        label=label,
        required=("id", "recorded_at", "decision", "scope", "rule_ids"),
        allowed=("id", "recorded_at", "decision", "scope", "rule_ids", "batch_reason"),
    )
    _require_string(record["id"], "{} id".format(label))
    _require_datetime(record["recorded_at"], "{} recorded_at".format(label))
    if record["decision"] not in CONFIRMATION_DECISIONS:
        raise ValueError("{} decision is unsupported".format(label))
    _require_string(record["scope"], "{} scope".format(label))
    _require_string_array(record["rule_ids"], "{} rule_ids".format(label), min_items=1, unique=True)
    if "batch_reason" in record:
        _require_string(record["batch_reason"], "{} batch_reason".format(label))
    return record


def _validate_manifest_adapter(value: object, index: int) -> Dict[str, object]:
    label = "Manifest adapter {}".format(index)
    record = _require_object(
        value,
        label=label,
        required=MANIFEST_ADAPTER_FIELDS,
        allowed=MANIFEST_ADAPTER_FIELDS,
    )
    for field in MANIFEST_ADAPTER_FIELDS[:-1]:
        _require_string(record[field], "{} {}".format(label, field))
    if record["support"] not in ADAPTER_SUPPORT_LEVELS:
        raise ValueError("{} support is unsupported".format(label))
    consumers = _require_string_array(
        record["consumers"], "{} consumers".format(label), min_items=1, unique=True
    )
    if record["id"] not in consumers:
        raise ValueError("{} consumers must include its owner id".format(label))
    return record


def load_manifest(path: Path) -> Dict[str, object]:
    """Load a final Manifest and enforce its complete normative schema."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Manifest is not valid JSON: {}".format(error)) from error
    manifest = _require_object(
        data,
        label="Manifest",
        required=("version", "project", "scan_baseline", "rules", "adapters", "confirmations"),
        allowed=("version", "project", "scan_baseline", "rules", "adapters", "confirmations"),
    )
    if manifest["version"] != "1.0":
        raise ValueError("Manifest version must be 1.0")

    project = _require_object(
        manifest["project"],
        label="Manifest project",
        required=("name", "language"),
        allowed=("name", "language"),
    )
    _require_string(project["name"], "Manifest project name")
    if project["language"] not in LANGUAGE_HEADINGS:
        raise ValueError("Manifest project language must be en or zh-CN")

    baseline = _require_object(
        manifest["scan_baseline"],
        label="Manifest scan_baseline",
        required=("kind", "captured_at", "paths"),
        allowed=("kind", "captured_at", "paths", "head", "fallback_reason"),
    )
    if baseline["kind"] not in {"git", "full-scan"}:
        raise ValueError("Manifest scan_baseline kind must be git or full-scan")
    _require_datetime(baseline["captured_at"], "Manifest scan_baseline captured_at")
    _require_string_array(baseline["paths"], "Manifest scan_baseline paths", unique=True)
    for field in ("head", "fallback_reason"):
        if field in baseline and baseline[field] is not None:
            _require_string(baseline[field], "Manifest scan_baseline {}".format(field))
    if baseline["kind"] == "git" and "head" not in baseline:
        raise ValueError("Git scan_baseline requires head")

    if not isinstance(manifest["rules"], list):
        raise ValueError("Manifest rules must be an array")
    rules = [_validate_rule(rule, index) for index, rule in enumerate(manifest["rules"])]
    rule_ids = [str(rule["id"]) for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise ValueError("Manifest rule IDs must be unique")
    constraint_confirmation_ids = [
        str(rule["confirmation_id"])
        for rule in rules
        if rule["type"] == "constraint"
    ]
    if len(constraint_confirmation_ids) != len(set(constraint_confirmation_ids)):
        raise ValueError("Every Manifest constraint requires a unique confirmation ID")
    rule_records = {str(rule["id"]): rule for rule in rules}
    for rule in rules:
        supersedes = rule.get("supersedes")
        if supersedes is not None and supersedes not in rule_records:
            raise ValueError("Manifest rule supersedes must reference another rule")

    if not isinstance(manifest["confirmations"], list):
        raise ValueError("Manifest confirmations must be an array")
    confirmations = [
        _validate_confirmation(item, index)
        for index, item in enumerate(manifest["confirmations"])
    ]
    confirmation_ids = [str(item["id"]) for item in confirmations]
    if len(confirmation_ids) != len(set(confirmation_ids)):
        raise ValueError("Manifest confirmation IDs must be unique")
    for record in confirmations:
        for rule_id in record["rule_ids"]:
            if rule_id not in rule_records:
                raise ValueError("Manifest confirmation references an unknown rule ID")

    if not isinstance(manifest["adapters"], list):
        raise ValueError("Manifest adapters must be an array")
    adapters = [
        _validate_manifest_adapter(item, index)
        for index, item in enumerate(manifest["adapters"])
    ]
    adapter_ids = [str(adapter["id"]) for adapter in adapters]
    if len(adapter_ids) != len(set(adapter_ids)):
        raise ValueError("Manifest adapter owner IDs must be unique")
    return manifest


def _rule_records(manifest: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    return {
        str(rule["id"]): rule
        for rule in manifest.get("rules", [])
        if isinstance(rule, dict)
    }


def _confirmation_records(manifest: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    return {
        str(record["id"]): record
        for record in manifest.get("confirmations", [])
        if isinstance(record, dict)
    }


def _sections(content: str) -> Dict[str, str]:
    matches = list(HEADING_PATTERN.finditer(content))
    sections: Dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group(1).strip()] = content[match.end():end]
    return sections


def _constraint_section_rule_ids(content: str) -> Tuple[List[str], int]:
    sections = _sections(content)
    bodies = [
        body
        for language in LANGUAGE_HEADINGS.values()
        for heading, body in sections.items()
        if heading == language["constraints"]
    ]
    marker_ids: List[str] = []
    missing_markers = 0
    for body in bodies:
        pending_marker: Optional[str] = None
        has_list_item = False
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            marker = RULE_ID_PATTERN.fullmatch(line)
            if marker is not None:
                if pending_marker is not None:
                    missing_markers += 1
                pending_marker = marker.group(1)
                continue
            if TOP_LEVEL_LIST_ITEM_PATTERN.match(raw_line):
                if pending_marker is None:
                    missing_markers += 1
                else:
                    marker_ids.append(pending_marker)
                pending_marker = None
                has_list_item = True
                continue
            if raw_line[:1].isspace() and has_list_item and pending_marker is None:
                continue
            missing_markers += 1
            pending_marker = None
        if pending_marker is not None:
            missing_markers += 1
    return marker_ids, missing_markers


def _canonical_scope_values(content: str) -> Set[str]:
    sections = _sections(content)
    values: Set[str] = set()
    for language in LANGUAGE_HEADINGS.values():
        body = sections.get(language["scope"])
        if body is None:
            continue
        for line in body.splitlines():
            normalized = re.sub(r"^[-*+]\s+", "", line.strip()).strip("`").strip()
            if normalized:
                values.add(normalized)
    return values


def _constraint_record_issues(
    rule_id: str,
    path: str,
    manifest: Mapping[str, object],
) -> List[ValidationIssue]:
    rule = _rule_records(manifest).get(rule_id)
    if rule is None or rule.get("type") != "constraint" or rule.get("status") != "confirmed":
        return [
            ValidationIssue(
                "unconfirmed-constraint",
                path,
                "Constraint '{}' is not a confirmed Manifest constraint".format(rule_id),
            )
        ]
    confirmation_id = str(rule.get("confirmation_id", ""))
    confirmation = _confirmation_records(manifest).get(confirmation_id)
    if confirmation is None or confirmation.get("decision") != "confirmed":
        return [
            ValidationIssue(
                "missing-constraint-confirmation",
                path,
                "Constraint '{}' lacks its explicit confirmed record '{}'".format(
                    rule_id, confirmation_id
                ),
            )
        ]
    issues: List[ValidationIssue] = []
    if rule_id not in confirmation.get("rule_ids", []):
        issues.append(
            ValidationIssue(
                "constraint-confirmation-rule-mismatch",
                path,
                "Confirmation '{}' does not list constraint '{}'".format(
                    confirmation_id, rule_id
                ),
            )
        )
    if confirmation.get("scope") != rule.get("scope"):
        issues.append(
            ValidationIssue(
                "constraint-confirmation-scope-mismatch",
                path,
                "Confirmation '{}' scope does not match constraint '{}'".format(
                    confirmation_id, rule_id
                ),
            )
        )
    confirmation_evidence = [
        item
        for item in rule.get("evidence", [])
        if isinstance(item, dict)
        and item.get("kind") == "user-confirmation"
        and item.get("location") == confirmation_id
    ]
    if not confirmation_evidence:
        issues.append(
            ValidationIssue(
                "constraint-confirmation-evidence-mismatch",
                path,
                "Constraint '{}' lacks evidence linked to confirmation '{}'".format(
                    rule_id, confirmation_id
                ),
            )
        )
    return issues


def validate_rule_file(path: Path, manifest: Dict[str, object]) -> List[ValidationIssue]:
    """Validate headings, rule identities, and constraints in one canonical file."""
    issue_path = path.as_posix()
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [
            ValidationIssue(
                "unreadable-rule-file",
                issue_path,
                "Cannot read rule file: {}".format(error),
            )
        ]
    language = str(manifest.get("project", {}).get("language", ""))
    expected = LANGUAGE_HEADINGS.get(language)
    issues: List[ValidationIssue] = []
    headings = set(HEADING_PATTERN.findall(content))
    if expected is not None and expected["scope"] not in headings:
        issues.append(
            ValidationIssue(
                "missing-scope",
                issue_path,
                "Canonical rule file is missing '## {}'".format(expected["scope"]),
            )
        )
    if expected is not None:
        for key in ("facts", "rules", "verification", "related"):
            if expected[key] not in headings:
                issues.append(
                    ValidationIssue(
                        "missing-heading",
                        issue_path,
                        "Canonical rule file is missing '## {}'".format(expected[key]),
                    )
                )
    other_headings = {
        heading
        for other_language, mapping in LANGUAGE_HEADINGS.items()
        if other_language != language
        for heading in mapping.values()
    }
    bilingual_headings = {
        "{}/{}".format(LANGUAGE_HEADINGS["zh-CN"][key], LANGUAGE_HEADINGS["en"][key])
        for key in LANGUAGE_HEADINGS["en"]
    }
    normalized_headings = {heading.replace(" / ", "/") for heading in headings}
    if headings & other_headings or normalized_headings & bilingual_headings:
        issues.append(
            ValidationIssue(
                "heading-language-mismatch",
                issue_path,
                "Canonical headings must use Manifest language '{}' only".format(language),
            )
        )
    if ADAPTER_SYNTAX_PATTERN.search(content):
        issues.append(
            ValidationIssue(
                "adapter-syntax-in-canonical-rule",
                issue_path,
                "Canonical rule file contains adapter-only frontmatter syntax",
            )
        )
    constraint_ids, missing_markers = _constraint_section_rule_ids(content)
    for _ in range(missing_markers):
        issues.append(
            ValidationIssue(
                "missing-constraint-marker",
                issue_path,
                "Every confirmed-constraint list item requires one preceding rule-id marker",
            )
        )
    all_ids = RULE_ID_PATTERN.findall(content)
    constraint_id_set = set(constraint_ids)
    records = _rule_records(manifest)
    scope_values = _canonical_scope_values(content)
    for rule_id in all_ids:
        rule = records.get(rule_id)
        if rule is None:
            issues.append(
                ValidationIssue(
                    "missing-manifest-rule",
                    issue_path,
                    "Canonical rule '{}' is absent from the Manifest".format(rule_id),
                )
            )
            continue
        if path.stem in DOMAIN_VALUES and rule.get("domain") != path.stem:
            issues.append(
                ValidationIssue(
                    "rule-domain-mismatch",
                    issue_path,
                    "Rule '{}' domain does not match '{}'".format(rule_id, path.stem),
                )
            )
        if rule.get("scope") not in scope_values:
            issues.append(
                ValidationIssue(
                    "rule-scope-mismatch",
                    issue_path,
                    "Rule '{}' scope is not declared by the canonical file".format(
                        rule_id
                    ),
                )
            )
        if rule.get("type") == "constraint" and rule_id not in constraint_id_set:
            issues.append(
                ValidationIssue(
                    "constraint-outside-confirmed-section",
                    issue_path,
                    "Constraint '{}' must be in the confirmed-constraints section".format(
                        rule_id
                    ),
                )
            )
    for rule_id in constraint_ids:
        issues.extend(_constraint_record_issues(rule_id, issue_path, manifest))
    return issues


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _canonical_rule_files(root: Path) -> List[Path]:
    canonical_root = root / CANONICAL_RULES_PATH
    if not canonical_root.is_dir():
        return []
    return sorted(path for path in canonical_root.rglob("*.md") if path.is_file())


def _adapter_metadata(content: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    frontmatter = FRONTMATTER_PATTERN.match(content)
    if frontmatter is not None:
        for line in frontmatter.group("body").splitlines():
            field = FRONTMATTER_FIELD_PATTERN.match(line)
            if field is not None:
                key, value = field.groups()
                if key in {
                    "adapter-id",
                    "adapter",
                    "tool-id",
                    "adapter-support",
                    "support",
                    "support-level",
                    "adapter-scope",
                    "adapter-loading",
                    "adapter-consumers",
                }:
                    metadata[key] = value
    for key, value in ADAPTER_METADATA_PATTERN.findall(content):
        metadata[key.lower()] = value.strip()
    return metadata


def _resolve_adapter_registry(registry: RegistryInput) -> Optional[Dict[str, object]]:
    if registry is None:
        if not BUNDLED_REGISTRY_PATH.is_file():
            return None
        return load_adapter_registry(BUNDLED_REGISTRY_PATH)
    if isinstance(registry, Path):
        return load_adapter_registry(registry)
    if isinstance(registry, dict):
        return validate_adapter_registry_data(registry)
    raise ValueError("Adapter registry must be a path or object")


def _manifest_adapter_issues(
    manifest: Dict[str, object], registry: Dict[str, object]
) -> Tuple[List[ValidationIssue], List[Dict[str, object]]]:
    records = adapter_registry_records(registry)
    issues: List[ValidationIssue] = []
    authorized: List[Dict[str, object]] = []
    path_owners: Dict[str, str] = {}
    field_codes = {
        "path": "adapter-path-mismatch",
        "template": "adapter-template-mismatch",
        "registry_version": "adapter-version-mismatch",
        "scope_loading": "adapter-scope-mismatch",
        "import_capability": "adapter-loading-mismatch",
        "support": "adapter-support-mismatch",
    }
    for adapter in manifest.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        adapter_id = str(adapter["id"])
        try:
            validate_relative_path(
                adapter["path"],
                allow_patterns=True,
                field="Manifest adapter path",
            )
        except ValueError as error:
            issues.append(
                ValidationIssue(
                    "unsafe-adapter-path", MANIFEST_PATH.as_posix(), str(error)
                )
            )
            continue
        try:
            validate_relative_path(
                adapter["template"],
                allow_patterns=False,
                field="Manifest adapter template",
            )
        except ValueError as error:
            issues.append(
                ValidationIssue(
                    "unsafe-adapter-template", MANIFEST_PATH.as_posix(), str(error)
                )
            )
            continue
        expected = records.get(adapter_id)
        if expected is None:
            issues.append(
                ValidationIssue(
                    "unknown-adapter-id",
                    MANIFEST_PATH.as_posix(),
                    "Manifest adapter '{}' is absent from the registry".format(adapter_id),
                )
            )
            continue
        mismatch = False
        expected_values = {
            "path": expected["path"],
            "template": expected["template"],
            "registry_version": registry["version"],
            "scope_loading": expected["scope_loading"],
            "import_capability": expected["import_capability"],
            "support": expected["support"],
        }
        for field, expected_value in expected_values.items():
            if adapter.get(field) != expected_value:
                mismatch = True
                issues.append(
                    ValidationIssue(
                        field_codes[field],
                        MANIFEST_PATH.as_posix(),
                        "Manifest adapter '{}' {} does not match the registry".format(
                            adapter_id, field
                        ),
                    )
                )
        consumers = adapter.get("consumers", [])
        try:
            resolved, unresolved = resolve_adapter_selection(registry, consumers)
        except ValueError:
            resolved, unresolved = [], list(consumers)
        if (
            unresolved
            or len(resolved) != 1
            or any(resolved[0].get(field) != adapter.get(field) for field in MANIFEST_ADAPTER_FIELDS)
        ):
            mismatch = True
            issues.append(
                ValidationIssue(
                    "adapter-shared-output-mismatch",
                    MANIFEST_PATH.as_posix(),
                    "Manifest adapter '{}' does not represent one resolved shared output".format(
                        adapter_id
                    ),
                )
            )
        output_path = str(adapter["path"])
        first_owner = path_owners.get(output_path)
        if first_owner is not None:
            mismatch = True
            issues.append(
                ValidationIssue(
                    "adapter-output-collision",
                    MANIFEST_PATH.as_posix(),
                    "Adapters '{}' and '{}' both own '{}'".format(
                        first_owner, adapter_id, output_path
                    ),
                )
            )
        else:
            path_owners[output_path] = adapter_id
        if not mismatch:
            authorized.append(adapter)
    return issues, authorized


def _path_matches_registry_pattern(relative_path: str, pattern: str) -> bool:
    expression = re.escape(pattern)
    expression = expression.replace(re.escape("<rule>"), r"[^/]+")
    expression = expression.replace(r"\*", r"[^/]+")
    return re.fullmatch(expression, relative_path) is not None


def _discover_registry_paths(
    root: Path, registry: Dict[str, object]
) -> Dict[str, List[Dict[str, object]]]:
    discovered: Dict[str, List[Dict[str, object]]] = {}
    for adapter in registry.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        pattern = str(adapter["path"])
        for path in root.glob(expand_registry_pattern(pattern)):
            if path.is_symlink():
                relative = _relative_path(root, path)
                if _path_matches_registry_pattern(relative, pattern):
                    discovered.setdefault(relative, []).append(adapter)
                continue
            if not path.is_file():
                continue
            relative = _relative_path(root, path)
            if _path_matches_registry_pattern(relative, pattern):
                discovered.setdefault(relative, []).append(adapter)
    return discovered


def _adapter_issues(
    root: Path,
    manifest: Dict[str, object],
    registry: Dict[str, object],
    authorized: List[Dict[str, object]],
    canonical_files: List[Path],
) -> List[ValidationIssue]:
    canonical_bodies: List[Tuple[str, str]] = []
    for path in canonical_files:
        try:
            body = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if len(body) >= 80:
            canonical_bodies.append((_relative_path(root, path), body))

    authorized_by_pattern = {str(adapter["path"]): adapter for adapter in authorized}
    issues: List[ValidationIssue] = []
    for relative, candidates in sorted(_discover_registry_paths(root, registry).items()):
        try:
            path = safe_target_path(root, relative)
        except ValueError as error:
            issues.append(ValidationIssue("unsafe-adapter-path", relative, str(error)))
            continue
        matching_authorized = [
            adapter
            for pattern, adapter in authorized_by_pattern.items()
            if _path_matches_registry_pattern(relative, pattern)
        ]
        expected_manifest = matching_authorized[0] if len(matching_authorized) == 1 else None
        if expected_manifest is not None and expected_manifest["support"] == "unverified":
            issues.append(
                ValidationIssue(
                    "unverified-adapter-output",
                    relative,
                    "Unverified adapters must not generate output",
                )
            )
            continue
        if expected_manifest is None and any(
            candidate.get("support") == "unverified" for candidate in candidates
        ):
            issues.append(
                ValidationIssue(
                    "unverified-adapter-output",
                    relative,
                    "Unverified adapters must not generate output",
                )
            )
            continue
        expected_registry: Optional[Dict[str, object]] = None
        if expected_manifest is not None:
            expected_registry = adapter_registry_records(registry).get(
                str(expected_manifest["id"])
            )
        elif len(candidates) == 1:
            expected_registry = candidates[0]
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            issues.append(
                ValidationIssue(
                    "unreadable-adapter-file",
                    relative,
                    "Cannot read adapter file: {}".format(error),
                )
            )
            continue
        metadata = _adapter_metadata(content)
        if expected_manifest is not None and expected_registry is not None:
            expected_metadata = {
                "adapter-id": str(expected_manifest["id"]),
                "adapter-support": str(expected_registry["support"]),
                "adapter-scope": str(expected_registry["scope_loading"]),
                "adapter-loading": str(expected_registry["import_capability"]),
                "adapter-consumers": ",".join(expected_manifest["consumers"]),
            }
            metadata_issue_codes = {
                "adapter-support": "adapter-support-mismatch",
                "adapter-scope": "adapter-scope-mismatch",
                "adapter-loading": "adapter-loading-mismatch",
            }
            for field, expected_value in expected_metadata.items():
                if metadata.get(field) != expected_value:
                    issues.append(
                        ValidationIssue(
                            metadata_issue_codes.get(field, "adapter-metadata-mismatch"),
                            relative,
                            "Adapter metadata '{}' must equal '{}'".format(
                                field, expected_value
                            ),
                        )
                    )
        for canonical_path, canonical_body in canonical_bodies:
            if canonical_body in content:
                issues.append(
                    ValidationIssue(
                        "adapter-content-duplication",
                        relative,
                        "Adapter copies the complete canonical rule body from '{}'".format(
                            canonical_path
                        ),
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
        manifest = {
            "project": {"language": "en"},
            "rules": [],
            "adapters": [],
            "confirmations": [],
        }

    try:
        adapter_registry = _resolve_adapter_registry(registry)
    except ValueError as error:
        issues.append(
            ValidationIssue(
                "invalid-adapter-registry", "references/adapters.json", str(error)
            )
        )
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
    seen_constraint_ids: Set[str] = set()
    for path in canonical_files:
        relative = _relative_path(root, path)
        for issue in validate_rule_file(path, manifest):
            issues.append(ValidationIssue(issue.code, relative, issue.message))
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        constraint_ids, _ = _constraint_section_rule_ids(content)
        seen_constraint_ids.update(constraint_ids)
        for rule_id in RULE_ID_PATTERN.findall(content):
            first_path = seen_rule_ids.get(rule_id)
            if first_path is not None:
                issues.append(
                    ValidationIssue(
                        "duplicate-rule-id",
                        relative,
                        "Rule ID '{}' is already defined in '{}'".format(
                            rule_id, first_path
                        ),
                    )
                )
            else:
                seen_rule_ids[rule_id] = relative

    for rule_id, rule in _rule_records(manifest).items():
        if rule_id not in seen_rule_ids:
            code = (
                "missing-constraint-marker"
                if rule.get("type") == "constraint"
                else "missing-canonical-rule-marker"
            )
            issues.append(
                ValidationIssue(
                    code,
                    CANONICAL_RULES_PATH.as_posix(),
                    "Manifest rule '{}' has no canonical rule-id marker".format(rule_id),
                )
            )
        if rule.get("type") == "constraint":
            if rule_id not in seen_constraint_ids:
                issues.append(
                    ValidationIssue(
                        "missing-constraint-marker",
                        CANONICAL_RULES_PATH.as_posix(),
                        "Constraint '{}' is absent from every confirmed-constraints section".format(
                            rule_id
                        ),
                    )
                )
            issues.extend(
                _constraint_record_issues(
                    rule_id, MANIFEST_PATH.as_posix(), manifest
                )
            )

    authorized: List[Dict[str, object]] = []
    if adapter_registry is not None:
        adapter_manifest_issues, authorized = _manifest_adapter_issues(
            manifest, adapter_registry
        )
        issues.extend(adapter_manifest_issues)
        issues.extend(
            _adapter_issues(
                root, manifest, adapter_registry, authorized, canonical_files
            )
        )
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
