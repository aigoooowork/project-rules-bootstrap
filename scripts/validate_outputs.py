"""Validate a generated v2 canonical rule tree."""

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.manifest import confirmed_constraints, load_manifest
from scripts.rule_contract import (
    LANGUAGE_HEADINGS,
    STRONG_CONSTRAINT_PATTERN,
    parse_confirmed_constraint_block,
)
from scripts.rule_quality import evaluate_rule_quality


ANALYSIS_PATH = ".ai/rules.analysis.md"
MANIFEST_PATH = ".ai/rules-manifest.json"
MARKER_PATTERN = re.compile(r"^<!-- rule-id: ([a-z0-9][a-z0-9._-]*) -->$")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def _issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code, path, message)


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _path_has_symlink(root: Path, relative: str) -> bool:
    current = root
    for part in relative.split("/"):
        current = current / part
        if os.path.lexists(str(current)) and current.is_symlink():
            return True
    return False


def _section_lines(text: str, language: str) -> List[tuple]:
    headings = LANGUAGE_HEADINGS[language]
    by_heading = {value: key for key, value in headings.items()}
    result = []
    section: Optional[str] = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = by_heading.get(line[3:].strip())
        result.append((section, line))
    return result


def _canonical_issues(
    path: str,
    text: str,
    language: str,
    confirmations: Mapping[str, Mapping[str, object]],
    found_constraints: Set[str],
) -> List[ValidationIssue]:
    issues = []
    headings = LANGUAGE_HEADINGS[language]
    lines = _section_lines(text, language)
    present = {section for section, _ in lines if section is not None}
    for required in ("scope", "facts", "rules", "verification", "related"):
        if required not in present:
            issues.append(
                _issue(
                    "missing-section",
                    path,
                    "canonical rule file is missing the {} section".format(
                        headings[required]
                    ),
                )
            )

    raw_lines = text.splitlines()
    constraint_lines: List[str] = []
    collecting_constraints = False
    for line in raw_lines:
        if line.startswith("## "):
            collecting_constraints = (
                line[3:].strip() == headings["constraints"]
            )
            continue
        if collecting_constraints:
            constraint_lines.append(line)
    if constraint_lines:
        try:
            parse_confirmed_constraint_block("\n".join(constraint_lines))
        except ValueError:
            issues.append(
                _issue(
                    "unconfirmed-constraint",
                    path,
                    "confirmed constraints require marker/list-item pairs",
                )
            )
    current_section: Optional[str] = None
    for index, line in enumerate(raw_lines):
        if line.startswith("## "):
            current_section = {
                value: key for key, value in headings.items()
            }.get(line[3:].strip())
            continue
        if STRONG_CONSTRAINT_PATTERN.search(line) and current_section != "constraints":
            issues.append(
                _issue(
                    "unconfirmed-strong-instruction",
                    path,
                    "strong instructions are allowed only in confirmed constraints",
                )
            )
        marker = MARKER_PATTERN.fullmatch(line.strip())
        if marker is None:
            continue
        rule_id = marker.group(1)
        if current_section != "constraints":
            issues.append(
                _issue("unconfirmed-constraint", path, "constraint marker is outside its section")
            )
            continue
        if rule_id in found_constraints:
            issues.append(_issue("duplicate-rule-id", path, "constraint rule ID is duplicated"))
            continue
        found_constraints.add(rule_id)
        body = raw_lines[index + 1].strip() if index + 1 < len(raw_lines) else ""
        if not body.startswith("- "):
            issues.append(
                _issue("invalid-constraint-body", path, "constraint marker requires one list item")
            )
            continue
        confirmation = confirmations.get(rule_id)
        if confirmation is None:
            issues.append(
                _issue("unconfirmed-constraint", path, "constraint has no confirmation record")
            )
            continue
        normalized = " ".join(body[2:].split()).encode("utf-8")
        if _digest(normalized) != confirmation.get("text_sha256"):
            issues.append(
                _issue(
                    "confirmation-text-mismatch",
                    path,
                    "constraint text does not match its confirmation record",
                )
            )
    return issues


def validate_output_tree(root: Path) -> List[ValidationIssue]:
    """Return concise issues without following symlinks or exposing file contents."""
    root = root.resolve()
    issues: List[ValidationIssue] = []
    manifest_path = root / MANIFEST_PATH
    if _path_has_symlink(root, MANIFEST_PATH) or not manifest_path.is_file():
        return [_issue("invalid-manifest", MANIFEST_PATH, "manifest is missing or unsafe")]
    try:
        manifest = load_manifest(manifest_path)
    except ValueError:
        return [_issue("invalid-manifest", MANIFEST_PATH, "manifest is invalid")]

    if os.path.lexists(str(root / ANALYSIS_PATH)):
        issues.append(
            _issue(
                "unexpected-analysis",
                ANALYSIS_PATH,
                "persistent analysis is not part of the v2 output contract",
            )
        )

    confirmations = confirmed_constraints(manifest)
    found_constraints: Set[str] = set()
    canonical_text: Dict[str, str] = {}
    for record in manifest["files"]:
        path = str(record["path"])
        target = root / path
        if _path_has_symlink(root, path) or not target.is_file():
            issues.append(_issue("unsafe-output", path, "owned output is missing or unsafe"))
            continue
        try:
            content = target.read_bytes()
        except OSError:
            issues.append(_issue("unsafe-output", path, "owned output is unreadable"))
            continue
        if _digest(content) != record["sha256"]:
            issues.append(_issue("hash-mismatch", path, "owned output hash has changed"))
        if record["kind"] != "canonical":
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(_issue("invalid-utf8", path, "canonical output must be UTF-8"))
            continue
        canonical_text[path] = text
        if path != ".ai/rules/index.md":
            issues.extend(
                _canonical_issues(
                    path,
                    text,
                    str(manifest["project"]["language"]),
                    confirmations,
                    found_constraints,
                )
            )
            quality = evaluate_rule_quality(root, text)
            if quality["issues"]:
                issues.append(
                    _issue(
                        "low-quality-rule",
                        path,
                        "canonical rule lacks grounded chain evidence: {}".format(
                            ", ".join(quality["issues"])
                        ),
                    )
                )

    index = canonical_text.get(".ai/rules/index.md")
    if index is None:
        issues.append(
            _issue("missing-index", ".ai/rules/index.md", "canonical index is required")
        )
    else:
        for path in canonical_text:
            if path == ".ai/rules/index.md":
                continue
            name = path.rsplit("/", 1)[-1]
            if "({})".format(name) not in index:
                issues.append(_issue("missing-index-link", path, "canonical file is not listed in index"))

    for rule_id in confirmations:
        if rule_id not in found_constraints:
            issues.append(
                _issue(
                    "missing-confirmed-rule",
                    MANIFEST_PATH,
                    "confirmation record has no canonical constraint marker",
                )
            )
    return issues


def main(argv: Optional[List[str]] = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("usage: validate_outputs.py <project-root>")
        return 2
    issues = validate_output_tree(Path(arguments[0]))
    for issue in issues:
        print("{} {}: {}".format(issue.code, issue.path, issue.message))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
