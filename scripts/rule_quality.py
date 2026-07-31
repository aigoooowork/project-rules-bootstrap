"""Measure whether canonical rules are grounded in an actual project."""

import re
import shlex
from pathlib import Path
from typing import Dict, List, Set


CODE_SPAN_PATTERN = re.compile(r"`([^`\n]+)`")
SYMBOL_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_.$:-]*\(\)$")
PATH_PATTERN = re.compile(
    r"^(?:(?:\.?[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+(?:\.[A-Za-z0-9_-]+)?"
    r"|[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+)$"
)
VERIFICATION_HEADING_PATTERN = re.compile(
    r"^##\s+(?:Verification|验证方式)\s*$", re.MULTILINE
)
NEXT_HEADING_PATTERN = re.compile(r"^##\s+", re.MULTILINE)
ROOT_FILE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".gradle",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kts",
    ".md",
    ".mjs",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
    ".vue",
}
COMMAND_PREFIXES = {
    "bash",
    "bundle",
    "cargo",
    "composer",
    "dotnet",
    "go",
    "gradle",
    "make",
    "mvn",
    "mypy",
    "npm",
    "npx",
    "pnpm",
    "pytest",
    "python",
    "python3",
    "ruff",
    "sh",
    "uv",
    "yarn",
}
MAX_SOURCE_FILE_BYTES = 512 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def _within_root(root: Path, relative: str) -> bool:
    try:
        (root / relative).resolve(strict=False).relative_to(
            root.resolve(strict=False)
        )
    except (OSError, ValueError):
        return False
    return True


def _path_tokens(code_span: str) -> List[str]:
    try:
        tokens = shlex.split(code_span)
    except ValueError:
        tokens = code_span.split()
    normalized = [
        token.lstrip("([{\"").rstrip(".,:;)]}\"") for token in tokens
    ]
    return [
        token
        for token in normalized
        if PATH_PATTERN.fullmatch(token)
        and ("/" in token or Path(token).suffix.lower() in ROOT_FILE_SUFFIXES)
    ]


def _verification_section(document: str) -> str:
    match = VERIFICATION_HEADING_PATTERN.search(document)
    if match is None:
        return ""
    start = match.end()
    following = NEXT_HEADING_PATTERN.search(document, start)
    return document[start : following.start() if following else len(document)]


def _symbol_name(value: str) -> str:
    return value[:-2].rsplit(".", 1)[-1].rsplit("::", 1)[-1]


def _verified_symbols(root: Path, paths: Set[str], candidates: Set[str]) -> Set[str]:
    remaining = MAX_SOURCE_BYTES
    bodies: List[str] = []
    for relative in sorted(paths):
        target = root / relative
        if target.suffix.lower() not in SOURCE_SUFFIXES or remaining <= 0:
            continue
        try:
            with target.open("rb") as handle:
                content = handle.read(min(MAX_SOURCE_FILE_BYTES, remaining))
        except OSError:
            continue
        remaining -= len(content)
        bodies.append(content.decode("utf-8", errors="ignore"))
    verified = set()
    for candidate in candidates:
        name = _symbol_name(candidate)
        pattern = re.compile(r"(?<![A-Za-z0-9_$]){}(?![A-Za-z0-9_$])".format(re.escape(name)))
        if any(pattern.search(body) for body in bodies):
            verified.add(candidate)
    return verified


def _is_command(root: Path, value: str) -> bool:
    try:
        tokens = shlex.split(value)
    except ValueError:
        return False
    if len(tokens) < 2:
        return False
    executable = tokens[0]
    if executable in COMMAND_PREFIXES:
        return True
    if executable.startswith("./"):
        target = root / executable[2:]
        return target.is_file()
    return False


def evaluate_rule_quality(root: Path, document: str) -> Dict[str, object]:
    """Return deterministic grounding signals and actionable quality issues."""
    project_root = root.resolve(strict=False)
    existing: Set[str] = set()
    missing: Set[str] = set()
    candidate_symbols: Set[str] = set()
    chain_candidates: List[Set[str]] = []

    for line in document.splitlines():
        spans = CODE_SPAN_PATTERN.findall(line)
        line_symbols = {span for span in spans if SYMBOL_PATTERN.fullmatch(span)}
        candidate_symbols.update(line_symbols)
        if ("→" in line or "->" in line) and len(line_symbols) >= 2:
            chain_candidates.append(line_symbols)
        for span in spans:
            if SYMBOL_PATTERN.fullmatch(span):
                continue
            for relative in _path_tokens(span):
                if not _within_root(project_root, relative):
                    missing.add(relative)
                    continue
                target = project_root / relative
                if target.is_file():
                    existing.add(relative)
                elif not target.exists():
                    missing.add(relative)

    symbols = _verified_symbols(project_root, existing, candidate_symbols)
    chain_signals = sum(
        1 for candidates in chain_candidates if len(candidates & symbols) >= 2
    )
    verification = _verification_section(document)
    verification_commands = sum(
        1
        for span in CODE_SPAN_PATTERN.findall(verification)
        if _is_command(project_root, span)
    )

    issues: List[str] = []
    if len(existing) < 2:
        issues.append("missing-existing-project-anchors")
    if len(symbols) < 2:
        issues.append("missing-code-symbol-anchors")
    if chain_signals == 0:
        issues.append("missing-complete-chain-signal")
    if verification_commands == 0:
        issues.append("missing-verification-command")
    if missing:
        issues.append("invented-project-anchors")

    return {
        "issues": issues,
        "existing_path_anchors": len(existing),
        "existing_path_anchor_paths": sorted(existing),
        "missing_path_anchors": sorted(missing),
        "candidate_symbol_anchors": len(candidate_symbols),
        "symbol_anchors": len(symbols),
        "chain_signals": chain_signals,
        "verification_commands": verification_commands,
    }
