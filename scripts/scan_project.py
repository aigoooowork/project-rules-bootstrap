"""Collect deterministic, bounded, read-only evidence about a local project."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple

try:
    import tomllib
except ImportError:  # Python 3.10 fallback keeps scanning available.
    tomllib = None


SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "secrets.py",
    "source_win_env.py",
}
IGNORED_DIRS = {
    ".git",
    ".worktrees",
    ".idea",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
}
SCANNED_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "manage.py",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
    ".python-version",
    ".nvmrc",
    "Dockerfile",
    "Makefile",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
    ".editorconfig",
    ".pre-commit-config.yaml",
    ".pre-commit-config.yml",
    ".golangci.yaml",
    ".golangci.yml",
    "tsconfig.json",
    "biome.json",
    "ruff.toml",
    ".ruff.toml",
    "checkstyle.xml",
}
SCANNED_NAMES_LOWER = {name.lower() for name in SCANNED_NAMES}
MODULE_MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
}
SOURCE_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".vue": "vue",
    ".java": "java",
    ".go": "go",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".rs": "rust",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
}
MAX_RULE_DISCOVERY_CANDIDATES_PER_MODULE = 12
MAX_RULE_DISCOVERY_CANDIDATES_PER_PARENT = 2
MAX_DIRECTORY_ENTRIES = 5000
MAX_FILES = 2000
MAX_FILE_BYTES = 64 * 1024
MAX_CONTENT_BYTES = 512 * 1024
MAX_GIT_OUTPUT_BYTES = 16 * 1024
MAX_GIT_STATUS_RECORDS = 200
MAX_GIT_COMMIT_RECORDS = 100
GIT_TIMEOUT_SECONDS = 5.0
PYTHON_BACKEND_FRAMEWORK_PATTERN = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9_-])(django|flask|fastapi|starlette|litestar)"
    r"(?:[^A-Za-z0-9_-]|$)"
)
KNOWN_FRAMEWORKS = {
    "django",
    "express",
    "fastapi",
    "fastify",
    "flask",
    "litestar",
    "nestjs",
    "starlette",
}


@dataclass(frozen=True)
class _GitCommandResult:
    returncode: int
    stdout: str
    truncated: bool


@dataclass(frozen=True)
class _CollectionResult:
    files: List[Path]
    entries_seen: int
    entries_truncated: bool
    files_truncated: bool
    depth_truncated: bool
    unverified: List[Dict[str, str]]
    unverified_summary: Dict[str, int]
    unverified_path_bytes: int
    unverified_paths_truncated: bool
    unverified_directories: List[str]


@dataclass(frozen=True)
class _BodyResult:
    content: str
    content_scanned: bool
    status: str
    truncated: bool
    bytes_read: int
    reason: Optional[str]


def classify_path(path: Path) -> str:
    """Return the scanner policy class for one filesystem path."""
    if path.name in SENSITIVE_NAMES or path.name.startswith(".env."):
        return "sensitive"
    if any(part in IGNORED_DIRS for part in path.parts):
        return "ignored"
    if path.is_symlink():
        return "symlink"
    return "file"


def is_within_root(path: Path, root: Path) -> bool:
    """Return whether a path resolves within the supplied project root."""
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except (OSError, ValueError):
        return False
    return True


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _safe_text(root: Path, path: Path) -> str:
    if classify_path(path) != "file" or not is_within_root(path, root):
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _package_dependencies(content: str) -> Set[str]:
    try:
        package = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return set()
    if not isinstance(package, dict):
        return set()
    dependencies: Set[str] = set()
    for section in ("dependencies", "peerDependencies"):
        values = package.get(section, {})
        if isinstance(values, dict):
            dependencies.update(str(name) for name in values)
    return dependencies


def detect_stack_signals(
    root: Path,
    files: List[Path],
    contents: Optional[Mapping[Path, str]] = None,
) -> Dict[str, List[str]]:
    """Identify direct framework and toolchain signals without architecture claims."""
    frontend: Set[str] = set()
    backend: Set[str] = set()
    toolchains: Set[str] = set()
    for path in files:
        if not is_within_root(path, root) or classify_path(path) != "file":
            continue
        content = contents.get(path, "") if contents is not None else _safe_text(root, path)
        if not content:
            continue
        name = path.name
        if name == "package.json":
            toolchains.add("node")
            dependencies = _package_dependencies(content)
            for framework in ("vue", "react", "angular", "svelte"):
                if framework in dependencies or (
                    framework == "angular" and "@angular/core" in dependencies
                ):
                    frontend.add(framework)
            for framework in ("express", "fastify", "nestjs"):
                dependency_name = "@nestjs/core" if framework == "nestjs" else framework
                if dependency_name in dependencies:
                    backend.add(framework)
        elif name in {"pyproject.toml", "requirements.txt", "Pipfile", "manage.py"}:
            toolchains.add("python")
            framework_content = content
            if name == "pyproject.toml":
                project_section = re.search(
                    r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", content
                )
                framework_content = project_section.group(1) if project_section else ""
            for match in PYTHON_BACKEND_FRAMEWORK_PATTERN.findall(framework_content):
                backend.add(match.lower())
        elif name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            toolchains.add("java")
        elif name == "go.mod":
            toolchains.add("go")
        elif name == "Cargo.toml":
            toolchains.add("rust")
    return {
        "frontend": sorted(frontend),
        "backend": sorted(backend),
        "toolchains": sorted(toolchains),
    }


def detect_modules(
    root: Path,
    files: List[Path],
    contents: Optional[Mapping[Path, str]] = None,
) -> List[Dict[str, object]]:
    """Return nested package/configuration roots as explicit module boundaries."""
    modules: List[Dict[str, object]] = []
    for path in files:
        if path.name not in MODULE_MANIFESTS:
            continue
        if classify_path(path) != "file" or not is_within_root(path, root):
            continue
        module_root = path.parent
        if module_root == root:
            continue
        modules.append(
            {
                "path": _relative_path(root, module_root),
                "manifest": _relative_path(root, path),
                "stack_signals": detect_stack_signals(root, [path], contents),
            }
        )
    return sorted(modules, key=lambda module: str(module["path"]))


def _source_language(path: Path) -> Optional[str]:
    return SOURCE_LANGUAGES.get(path.suffix.lower())


def _project_relative_path(path: Path, root: Optional[Path]) -> Path:
    if root is None:
        return path
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _is_config_tooling(path: Path, root: Optional[Path] = None) -> bool:
    """Recognize repository-owned configuration and executable tooling inputs."""
    project_path = _project_relative_path(path, root)
    name = project_path.name.lower()
    relative = project_path.as_posix().lower()
    parts = {part.lower() for part in project_path.parts}
    if path.name in SCANNED_NAMES or name in SCANNED_NAMES_LOWER:
        return True
    if path.suffix.lower() in {".csproj", ".props", ".targets"}:
        return True
    if ".github/workflows/" in relative and path.suffix.lower() in {".yml", ".yaml"}:
        return True
    if "scripts" in parts and path.suffix.lower() in {".sh", ".ps1", ".bat", ".cmd"}:
        return True
    if name.startswith(
        ("tsconfig", ".eslintrc", ".prettierrc", "eslint.config.", "prettier.config.")
    ):
        return True
    if name.startswith(("checkstyle", "pmd", "spotbugs")) and path.suffix.lower() in {
        ".xml",
        ".yml",
        ".yaml",
    }:
        return True
    return False


def _role_hints(path: Path, root: Optional[Path] = None) -> List[str]:
    project_path = _project_relative_path(path, root)
    relative = project_path.as_posix().lower()
    name = project_path.name.lower()
    stem = project_path.stem.lower()
    parts = {part.lower() for part in project_path.parts}
    roles: Set[str] = set()

    if (
        stem in {"main", "manage", "application", "app", "program"}
        or "cmd" in parts
        or name in {"flask_run.py", "uwsgi_app.py"}
    ):
        roles.add("entry")
    if any(
        token in relative
        for token in (
            "controller",
            "handler",
            "resource",
            "routes",
            "router",
            "routing",
            "/views/",
            "/view/",
            "/pages/",
            "/api/",
            "/http/",
            "res_",
        )
    ):
        roles.add("interface")
    if any(
        token in relative
        for token in ("parser", "schema", "validator", "validation", "dto")
    ):
        roles.add("validation")
    if any(
        token in relative
        for token in ("service", "usecase", "use_case", "/domain/", "/business/")
    ):
        roles.add("business")
    if any(
        token in relative
        for token in (
            "repository",
            "/dao/",
            "mapper",
            "/models/",
            "/model/",
            "/sql/",
        )
    ):
        roles.add("data")
    if any(
        token in relative
        for token in (
            "middleware",
            "/common/",
            "/utils/",
            "/util/",
            "/config/",
            "/client/",
        )
    ):
        roles.add("shared")
    if (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or "spec" in parts
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith(("_test.go", "test.java", ".spec.js", ".spec.ts"))
    ):
        roles.add("test")
    return sorted(roles)


def _module_roots(root: Path, files: List[Path]) -> List[Path]:
    roots = sorted(
        {
            path.parent
            for path in files
            if path.name in MODULE_MANIFESTS and path.parent != root
        },
        key=lambda path: (len(path.parts), _relative_path(root, path)),
        reverse=True,
    )
    return roots


def _candidate_module(root: Path, path: Path, module_roots: List[Path]) -> str:
    for module_root in module_roots:
        try:
            path.relative_to(module_root)
        except ValueError:
            continue
        return _relative_path(root, module_root)
    relative = path.relative_to(root)
    return relative.parts[0] if len(relative.parts) > 1 else "."


def _candidate_quality(path: Path, roles: List[str]) -> int:
    """Prefer effective implementation points over broad or package-only files."""
    name = path.name.lower()
    stem = path.stem.lower()
    score = len(roles) * 10
    if name in {"service.py", "repository.py", "repository_ops.py"}:
        score += 100
    elif name in {"views_resource.py", "routes.py", "router.js", "router.ts"}:
        score += 90
    elif name in {"routing.py", "applications.py", "dependencies.py"}:
        score += 95
    elif name.startswith("res_") or name.endswith(("_handler.go", "controller.java")):
        score += 85
    elif any(token in stem for token in ("parser", "validation", "validator", "schema")):
        score += 80
    elif name in {"http.js", "http.ts", "business.js", "business.ts", "client.js", "client.ts"}:
        score += 80
    if "test" in roles and name not in {"__init__.py", "conftest.py"}:
        score += 75
    if name in {"main.py", "main.go", "app.py", "flask_run.py", "manage.py"}:
        score += 60
    if stem in {"runtime_services", "common", "utils", "config"}:
        score -= 20
    return score


def _scan_priority(path: Path, roles: List[str], root: Optional[Path] = None) -> str:
    project_path = _project_relative_path(path, root)
    parts = {part.lower() for part in project_path.parts}
    if parts & {"docs", "docs_src", "examples", "example", "samples"}:
        return "docs-example"
    if "test" in roles:
        return "test"
    if _is_config_tooling(path, root):
        return "config-tooling"
    if _source_language(path) is not None:
        return "primary-source"
    return "other"


def _read_priority(root: Path, path: Path) -> Tuple[int, str]:
    priority = _scan_priority(path, _role_hints(path, root), root)
    order = {
        "primary-source": 0,
        "test": 1,
        "config-tooling": 2,
        "docs-example": 3,
        "other": 4,
    }
    return order[priority], path.as_posix()


def select_rule_discovery_candidates(
    root: Path,
    files: List[Path],
    *,
    max_candidates_per_module: int = MAX_RULE_DISCOVERY_CANDIDATES_PER_MODULE,
) -> Dict[str, object]:
    """Select representative source files without claiming a precise call graph."""
    module_roots = _module_roots(root, files)
    by_module: Dict[str, List[Dict[str, object]]] = {}
    for path in files:
        language = _source_language(path)
        config_tooling = _is_config_tooling(path, root)
        if language is None and not config_tooling:
            continue
        if path.name.lower() == "__init__.py":
            continue
        if classify_path(path) != "file" or not is_within_root(path, root):
            continue
        roles = _role_hints(path, root)
        if config_tooling and "tooling" not in roles:
            roles.append("tooling")
            roles.sort()
        module = _candidate_module(root, path, module_roots)
        by_module.setdefault(module, []).append(
            {
                "path": _relative_path(root, path),
                "module": module,
                "language": language or "configuration",
                "role_hints": roles,
                "selection_reason": (
                    "tooling-evidence"
                    if config_tooling
                    else ("role-coverage" if roles else "comparable-source")
                ),
                "scan_priority": _scan_priority(path, roles, root),
                "_quality": _candidate_quality(path, roles),
            }
        )

    selected: List[Dict[str, object]] = []
    uncovered_roles: Dict[str, List[str]] = {}
    all_roles = {
        role
        for candidates in by_module.values()
        for candidate in candidates
        for role in candidate["role_hints"]
    }
    for module in sorted(by_module):
        priority_order = {
            "primary-source": 0,
            "test": 1,
            "config-tooling": 2,
            "docs-example": 3,
            "other": 4,
        }
        candidates = sorted(
            by_module[module],
            key=lambda item: (
                priority_order[str(item["scan_priority"])],
                -int(item["_quality"]),
                str(item["path"]),
            ),
        )
        module_selected: List[Dict[str, object]] = []
        covered: Set[str] = set()
        for candidate in candidates:
            new_roles = set(candidate["role_hints"]) - covered
            # Preserve the highest-priority project evidence even when the
            # filename does not imply one of the known architectural roles.
            # Otherwise a docs/example route can displace a real source file.
            if not new_roles and module_selected:
                continue
            module_selected.append(candidate)
            covered.update(candidate["role_hints"])
            if len(module_selected) >= max_candidates_per_module:
                break
        if len(module_selected) < max_candidates_per_module:
            selected_paths = {str(item["path"]) for item in module_selected}
            parent_counts: Dict[Tuple[str, str], int] = {}
            for item in module_selected:
                parent = str(Path(str(item["path"])).parent)
                parent_key = (parent, str(item["scan_priority"]))
                parent_counts[parent_key] = parent_counts.get(parent_key, 0) + 1
            for candidate in candidates:
                if str(candidate["path"]) in selected_paths:
                    continue
                parent = str(Path(str(candidate["path"])).parent)
                parent_key = (parent, str(candidate["scan_priority"]))
                parent_limit = (
                    8
                    if candidate["scan_priority"] == "config-tooling"
                    else MAX_RULE_DISCOVERY_CANDIDATES_PER_PARENT
                )
                if parent_counts.get(parent_key, 0) >= parent_limit:
                    continue
                module_selected.append(candidate)
                parent_counts[parent_key] = parent_counts.get(parent_key, 0) + 1
                if len(module_selected) >= max_candidates_per_module:
                    break
        for candidate in module_selected:
            candidate.pop("_quality", None)
        selected.extend(module_selected)
        missing = sorted(all_roles - covered)
        if missing:
            uncovered_roles[module] = missing

    return {
        "candidates": selected,
        "uncovered_modules": [],
        "uncovered_roles": uncovered_roles,
        "selection_limit_per_module": max_candidates_per_module,
        "claim": "representative-candidates-not-a-complete-call-graph",
    }


def detect_development_convention_evidence(
    root: Path,
    candidates: List[Dict[str, object]],
    contents: Mapping[Path, str],
) -> Dict[str, object]:
    """Route convention discovery without asserting a language's default style."""
    readable = [item for item in candidates if item.get("content_scanned")]
    primary = [item for item in readable if item.get("scan_priority") == "primary-source"]
    tests = [item for item in readable if item.get("scan_priority") == "test"]
    configs = [item for item in readable if item.get("scan_priority") == "config-tooling"]
    docs = [item for item in readable if item.get("scan_priority") == "docs-example"]

    def body(item: Dict[str, object]) -> str:
        relative = Path(*str(item["path"]).split("/"))
        return contents.get(root / relative, "")
    languages = sorted(
        {
            str(item["language"])
            for item in primary + tests
            if item.get("language") not in {None, "configuration"}
        }
    )

    def paths(items: List[Dict[str, object]], limit: int = 8) -> List[str]:
        return sorted({str(item["path"]) for item in items})[:limit]

    def combined_paths(
        *groups: Tuple[List[Dict[str, object]], int], limit: int = 8
    ) -> List[str]:
        result: List[str] = []
        for items, group_limit in groups:
            for value in paths(items, group_limit):
                if value not in result:
                    result.append(value)
                if len(result) >= limit:
                    return result
        return result

    evidence_sources: Dict[str, List[str]] = {}
    declaration_pattern = re.compile(
        r"\b(?:def|class|func|function|interface|type|const|let|var|record|enum|struct|trait|fn)\s+([A-Za-z_$][A-Za-z0-9_$]*)"
    )
    declarations = {
        match.group(1)
        for item in primary
        for match in declaration_pattern.finditer(body(item))
    }
    if len(primary) >= 2 and len(declarations) >= 6:
        evidence_sources["naming-and-case"] = paths(primary)
    error_pattern = re.compile(
        r"\b(?:raise|except|throw|catch|panic|recover|logger|logging)\b|"
        r"\b(?:Error|Exception)\b|(?:fmt|errors)\.(?:Errorf|New)|\blog\."
    )
    error_sources = [item for item in primary if error_pattern.search(body(item))]
    if len(error_sources) >= 2:
        evidence_sources["errors-logging-and-comments"] = paths(error_sources)
    if configs:
        style_tokens = (
            "ruff",
            "black",
            "isort",
            "eslint",
            "prettier",
            "biome",
            "golangci",
            "checkstyle",
            "spotless",
            "pmd",
            "editorconfig",
            "pre-commit",
            "pyproject",
            "tsconfig",
            "lint",
            "format",
        )
        style_configs = [
            item
            for item in configs
            if any(token in str(item["path"]).lower() for token in style_tokens)
        ]
        if style_configs:
            evidence_sources["formatting-and-imports"] = combined_paths(
                (style_configs, 4), (primary, 4)
            )
        build_tokens = (
            "package.json",
            "pyproject.toml",
            "requirements",
            "pipfile",
            "pom.xml",
            "build.gradle",
            "go.mod",
            "cargo.toml",
            "dockerfile",
            "compose",
            "makefile",
            ".python-version",
            ".nvmrc",
            "test.",
            "build.",
        )
        build_configs = [
            item
            for item in configs
            if any(token in str(item["path"]).lower() for token in build_tokens)
        ]
        evidence_sources["build-and-runtime"] = combined_paths(
            (build_configs or configs, 4), (configs, 4)
        )
    type_config_pattern = re.compile(
        r"(?i)\bmypy\b|\bpyright\b|"
        r"[\"']strict[\"']\s*:\s*true|noUncheckedIndexedAccess|"
        r"\bnullaway\b|checkerframework|errorprone|"
        r"<Nullable>\s*enable\s*</Nullable>|"
        r"<TreatWarningsAsErrors>\s*true\s*</TreatWarningsAsErrors>|"
        r"allWarningsAsErrors|explicitApi|(?:-Xjsr305=)strict"
    )
    type_source_pattern = re.compile(
        r"\b(?:interface|struct|record|Protocol|TypedDict|BaseModel|dataclass)\b|"
        r"->\s*[A-Za-z_]|\b(?:Promise|Optional|Result|Either)<"
    )
    type_configs = [item for item in configs if type_config_pattern.search(body(item))]
    type_sources = [item for item in primary if type_source_pattern.search(body(item))]
    if type_configs or len(type_sources) >= 2:
        evidence_sources["types-and-contracts"] = combined_paths(
            (type_configs, 2), (type_sources, 4), (tests, 2)
        )
    if tests:
        evidence_sources["tests"] = combined_paths((tests, 4), (primary, 4))
    interface = [
        item for item in primary if "interface" in item.get("role_hints", [])
    ]
    public_pattern = re.compile(
        r"\b(?:export|public)\b|\b(?:router|route)\b|"
        r"\.use\s*\(|\.(?:get|post|put|patch|delete)\s*\(|"
        r"@(?:Get|Post|Put|Patch|Delete|Request)Mapping\b|HandleFunc\s*\("
    )
    public_interfaces = [item for item in interface if public_pattern.search(body(item))]
    if public_interfaces and (len(public_interfaces) >= 2 or tests):
        evidence_sources["public-api-and-compatibility"] = combined_paths(
            (public_interfaces, 4), (tests, 4)
        )
    generated_inputs = [
        item
        for item in configs
        if any(
            token in str(item["path"]).lower()
            for token in ("doc", "generate", "schema", "openapi")
        )
    ]
    if docs or generated_inputs:
        evidence_sources["generated-docs-and-artifacts"] = paths(
            docs + generated_inputs
        )
    return {
        "languages": languages,
        "applicable_dimensions": sorted(evidence_sources),
        "evidence_sources": dict(sorted(evidence_sources.items())),
        "claim": "discovery-routing-not-proven-conventions",
    }


def detect_convention_recovery_targets(
    root: Path,
    files: List[Path],
    candidates: List[Dict[str, object]],
) -> Dict[str, List[str]]:
    """Name high-value unread convention anchors after a bounded partial scan."""
    readable = {
        str(item["path"]) for item in candidates if item.get("content_scanned")
    }
    safe_paths = [
        path
        for path in files
        if classify_path(path) == "file" and is_within_root(path, root)
    ]

    def select(predicate, limit: int = 8) -> List[str]:
        values = []
        for path in safe_paths:
            relative = _relative_path(root, path)
            roles = _role_hints(path, root)
            if (
                relative in readable
                or _scan_priority(path, roles, root) == "docs-example"
                or not predicate(path, relative.lower())
            ):
                continue
            values.append((_read_priority(root, path), relative))
        return [
            relative
            for _, relative in sorted(set(values), key=lambda item: item[0])[:limit]
        ]

    public_names = {
        "__init__.py",
        "assemblyinfo.cs",
        "doc.go",
        "exports.go",
        "index.js",
        "index.ts",
        "index.tsx",
        "lib.rs",
        "module-info.java",
        "package-info.java",
    }
    public_targets = select(
        lambda path, relative: path.name.lower() in public_names
        or any(token in relative for token in ("deprecat", "compat", "public", "export")),
        limit=4,
    )
    test_targets = select(
        lambda path, relative: "test" in _role_hints(path, root)
        and any(token in relative for token in ("deprecat", "compat", "public", "export")),
        limit=4,
    )
    config_targets = select(
        lambda path, relative: _is_config_tooling(path, root), limit=32
    )

    def config_recovery_priority(relative: str) -> Tuple[int, str]:
        lowered = relative.lower()
        name = Path(relative).name.lower()
        if name in SCANNED_NAMES_LOWER or any(
            token in lowered for token in ("/scripts/", "checkstyle", "eslint", "prettier")
        ):
            return 0, relative
        workflow_gate = re.search(
            r"(?:^|[-_.])(?:build|ci|docs|format|lint|pre-commit|test)(?:[-_.]|$)",
            name,
        )
        if ".github/workflows/" in lowered and workflow_gate is not None:
            return 1, relative
        if ".github/workflows/" in lowered and any(
            token in name for token in ("publish", "release")
        ):
            return 2, relative
        return 3, relative

    config_targets = sorted(config_targets, key=config_recovery_priority)[:8]
    recovery: Dict[str, List[str]] = {}
    combined_public = list(public_targets)
    combined_public.extend(
        target for target in test_targets if target not in combined_public
    )
    if combined_public:
        recovery["public-api-and-compatibility"] = combined_public
    if config_targets:
        recovery["formatting-build-and-runtime"] = config_targets
    return recovery


def detect_project_evidence(
    root: Path,
    files: List[Path],
    contents: Mapping[Path, str],
    stack_signals: Mapping[str, List[str]],
) -> Dict[str, object]:
    """Extract bounded declarations without claiming the external runtime matches them."""
    runtimes: List[Dict[str, str]] = []
    dependencies: List[Dict[str, str]] = []
    commands: List[Dict[str, str]] = []
    environment_sources: List[Dict[str, str]] = []
    runtime_dependency_names: Set[str] = set()
    project_identity: Dict[str, str] = {}
    primary_frameworks: Set[str] = set()
    package_managers: Set[str] = set()

    lockfile_managers = {
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
        "npm-shrinkwrap.json": "npm",
    }
    for manifest_path in files:
        manager = lockfile_managers.get(manifest_path.name)
        if manager:
            package_managers.add(manager)

    def add_named_dependency(
        name: object, version: object, source: str, scope: str
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            return
        normalized_name = name.strip()
        dependencies.append(
            {
                "name": normalized_name,
                "version": str(version).strip() or "unspecified",
                "source": source,
                "scope": scope,
            }
        )
        if scope in {"runtime", "peer"}:
            runtime_dependency_names.add(normalized_name.lower())

    def add_dependency(value: object, source: str, scope: str) -> None:
        if not isinstance(value, str):
            return
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)$", value.strip())
        if match is None:
            return
        name, version = match.groups()
        add_named_dependency(name, version or "unspecified", source, scope)

    for path in files:
        relative = _relative_path(root, path)
        lower_name = path.name.lower()
        content = contents.get(path, "")
        if lower_name.startswith(".env") or lower_name in {
            "dockerfile",
            "compose.yaml",
            "compose.yml",
            "docker-compose.yaml",
            "docker-compose.yml",
        } or any(part.lower() in {"config", "settings"} for part in path.parts):
            environment_sources.append(
                {"path": relative, "kind": "declared-config-source"}
            )
        if path.suffix == ".sh" and "scripts" in {part.lower() for part in path.parts}:
            if path.name.lower() in {"test.sh", "tests.sh", "lint.sh", "format.sh", "build.sh"}:
                commands.append({"command": "bash {}".format(relative), "source": relative, "working_directory": "."})
        if not content:
            continue
        if path.name == ".python-version":
            value = content.strip().splitlines()[0] if content.strip() else ""
            if value:
                runtimes.append({"runtime": "python", "value": value, "source": relative})
        elif path.name == ".nvmrc":
            value = content.strip().splitlines()[0] if content.strip() else ""
            if value:
                runtimes.append({"runtime": "node", "value": value, "source": relative})
        elif path.name == "Dockerfile":
            for match in re.finditer(r"(?im)^FROM\s+([^\s]+)", content):
                runtimes.append({"runtime": "container", "value": match.group(1), "source": relative})
        elif path.name == "package.json":
            try:
                package = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                package = {}
            if isinstance(package, dict):
                declared_manager = package.get("packageManager")
                local_manager = "npm"
                if isinstance(declared_manager, str) and declared_manager:
                    local_manager = declared_manager.split("@", 1)[0]
                    package_managers.add(local_manager)
                else:
                    for lockfile_name, manager_name in lockfile_managers.items():
                        if (path.parent / lockfile_name).is_file():
                            local_manager = manager_name
                            package_managers.add(local_manager)
                            break
                engines = package.get("engines", {})
                if isinstance(engines, dict):
                    for runtime in ("node", "npm", "pnpm"):
                        if isinstance(engines.get(runtime), str):
                            runtimes.append({"runtime": runtime, "value": engines[runtime], "source": relative})
                section_scopes = {
                    "dependencies": "runtime",
                    "devDependencies": "development",
                    "peerDependencies": "peer",
                }
                for section, scope in section_scopes.items():
                    values = package.get(section, {})
                    if isinstance(values, dict):
                        for name, version in values.items():
                            add_named_dependency(str(name), str(version), relative, scope)
                scripts = package.get("scripts", {})
                if isinstance(scripts, dict):
                    for name in sorted(scripts):
                        commands.append({"command": "{} run {}".format(local_manager, name), "source": relative, "working_directory": path.parent.relative_to(root).as_posix() or "."})
        if path.name == "pyproject.toml":
            parsed = {}
            if tomllib is not None:
                try:
                    parsed = tomllib.loads(content)
                except (ValueError, TypeError):
                    parsed = {}
            project = parsed.get("project", {}) if isinstance(parsed, dict) else {}
            if isinstance(project, dict):
                name = project.get("name")
                if isinstance(name, str):
                    project_identity = {"name": name, "source": relative}
                    if name.lower() in KNOWN_FRAMEWORKS and (root / name).is_dir():
                        primary_frameworks.add(name.lower())
                python_value = project.get("requires-python")
                if isinstance(python_value, str):
                    runtimes.append({"runtime": "python", "value": python_value, "source": relative})
                for dependency in project.get("dependencies", []):
                    add_dependency(dependency, relative, "runtime")
                optional = project.get("optional-dependencies", {})
                if isinstance(optional, dict):
                    for group_name, group in optional.items():
                        if isinstance(group_name, str) and isinstance(group, list):
                            for dependency in group:
                                add_dependency(dependency, relative, "optional:{}".format(group_name))
                entry_points = project.get("scripts", {})
                if isinstance(entry_points, dict):
                    for name in sorted(entry_points):
                        commands.append({"command": name, "source": relative, "working_directory": path.parent.relative_to(root).as_posix() or "."})
            else:
                python_match = re.search(r"(?m)^requires-python\s*=\s*[\"']([^\"']+)", content)
                if python_match:
                    runtimes.append({"runtime": "python", "value": python_match.group(1), "source": relative})
            poe = re.search(r"(?ms)^\[tool\.poe\.tasks\]\s*(.*?)(?=^\[|\Z)", content)
            if poe:
                for _name, command in re.findall(r"(?m)^([A-Za-z0-9_.-]+)\s*=\s*[\"']([^\"']+)[\"']", poe.group(1)):
                    commands.append({"command": command, "source": relative, "working_directory": path.parent.relative_to(root).as_posix() or "."})
        if path.name == "requirements.txt":
            for line in content.splitlines():
                value = line.strip()
                if value and not value.startswith(("#", "-")):
                    add_dependency(value.split(";", 1)[0], relative, "runtime")
        if path.name == "Pipfile":
            section = "runtime"
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == "[dev-packages]":
                    section = "development"
                elif stripped == "[packages]":
                    section = "runtime"
                else:
                    match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*[\"']?([^\"']+)", stripped)
                    if match:
                        add_named_dependency(match.group(1), match.group(2), relative, section)
        if path.name == "go.mod":
            for name, version in re.findall(
                r"(?m)^\s*(?:require\s+)?([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)\s+(v[^\s]+)",
                content,
            ):
                add_named_dependency(name, version, relative, "runtime")
        if path.name == "Cargo.toml" and tomllib is not None:
            try:
                cargo = tomllib.loads(content)
            except (ValueError, TypeError):
                cargo = {}
            if isinstance(cargo, dict):
                for section_name, scope in (("dependencies", "runtime"), ("dev-dependencies", "development")):
                    section = cargo.get(section_name, {})
                    if isinstance(section, dict):
                        for name, value in section.items():
                            version = value.get("version", "unspecified") if isinstance(value, dict) else value
                            add_named_dependency(name, version, relative, scope)
        if path.name == "pom.xml":
            for block in re.findall(r"(?s)<dependency>(.*?)</dependency>", content):
                artifact = re.search(r"<artifactId>([^<]+)</artifactId>", block)
                group = re.search(r"<groupId>([^<]+)</groupId>", block)
                version = re.search(r"<version>([^<]+)</version>", block)
                scope_match = re.search(r"<scope>([^<]+)</scope>", block)
                if artifact:
                    name = "{}:{}".format(group.group(1), artifact.group(1)) if group else artifact.group(1)
                    scope = "development" if scope_match and scope_match.group(1) == "test" else "runtime"
                    add_named_dependency(name, version.group(1) if version else "unspecified", relative, scope)
        if path.name in {"build.gradle", "build.gradle.kts"}:
            for configuration, name, version in re.findall(
                r"(?m)^\s*(implementation|api|testImplementation)\s*\(?[\"']([^:\"']+:[^:\"']+):([^\"']+)[\"']",
                content,
            ):
                scope = "development" if configuration == "testImplementation" else "runtime"
                add_named_dependency(name, version, relative, scope)
        if path.name == "Makefile":
            for target in re.findall(r"(?m)^([A-Za-z0-9_.-]+):(?:\s|$)", content):
                if not target.startswith("."):
                    commands.append({"command": "make {}".format(target), "source": relative, "working_directory": path.parent.relative_to(root).as_posix() or "."})

    specialties: Set[str] = set()
    api_dependency_names = {
        "express",
        "fastify",
        "@nestjs/core",
        "fastapi",
        "flask",
        "django",
        "github.com/gin-gonic/gin",
        "org.springframework:spring-web",
        "org.springframework:spring-webmvc",
        "org.springframework:spring-webflux",
    }
    database_dependency_names = {
        "sqlalchemy",
        "sqlmodel",
        "django",
        "prisma",
        "sequelize",
        "typeorm",
        "gorm.io/gorm",
        "org.hibernate.orm:hibernate-core",
        "org.hibernate:hibernate-core",
    }
    if stack_signals.get("backend") or runtime_dependency_names & api_dependency_names:
        specialties.add("api")
    if stack_signals.get("frontend"):
        specialties.add("frontend")
    if runtime_dependency_names & database_dependency_names:
        specialties.add("database")
    if runtime_dependency_names & {"openai", "anthropic", "langchain", "llama-index", "llamaindex", "chromadb", "qdrant-client"}:
        specialties.add("ai")
    return {
        "runtime_declarations": sorted(runtimes, key=lambda item: (item["source"], item["runtime"], item["value"])),
        "dependency_declarations": sorted(dependencies, key=lambda item: (item["source"], item["scope"], item["name"], item["version"])),
        "environment_sources": sorted(environment_sources, key=lambda item: item["path"]),
        "command_candidates": sorted(commands, key=lambda item: (item["source"], item["command"])),
        "project_identity": project_identity,
        "primary_frameworks": sorted(primary_frameworks),
        "package_managers": sorted(package_managers),
        "specialized_discovery": sorted(specialties),
    }


def _bounded_directory_entries(
    directory: Path, remaining: int
) -> Tuple[List[os.DirEntry], bool]:
    entries: List[os.DirEntry] = []
    truncated = False
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if len(entries) >= remaining:
                    truncated = True
                    break
                entries.append(entry)
    except OSError:
        raise
    return sorted(entries, key=lambda entry: entry.name), truncated


def _directory_priority(path: Path) -> Tuple[int, str]:
    parts = {part.lower() for part in path.parts}
    if parts & {"docs", "docs_src", "examples", "example", "samples"}:
        return 3, path.as_posix()
    if parts & {"tests", "test", "__tests__"}:
        return 1, path.as_posix()
    return 0, path.as_posix()


def _collect_files(
    root: Path,
    max_depth: int,
    max_entries: int,
    max_files: int,
    max_unverified_path_bytes: int,
) -> _CollectionResult:
    files: List[Path] = []
    pending: List[Path] = [root]
    entries_seen = 0
    entries_truncated = False
    files_truncated = False
    depth_truncated = False
    unverified: List[Dict[str, str]] = []
    unverified_summary: Dict[str, int] = {}
    unverified_path_bytes = 0
    unverified_paths_truncated = False
    unverified_directories: List[str] = []

    def record_unverified(path: Path, reason: str, *, directory: bool = False) -> None:
        nonlocal unverified_path_bytes, unverified_paths_truncated
        relative = _relative_path(root, path) or "."
        unverified_summary[reason] = unverified_summary.get(reason, 0) + 1
        if directory:
            unverified_directories.append(relative)
        path_bytes = len(relative.encode("utf-8"))
        if (
            len(unverified) >= max_entries
            or unverified_path_bytes + path_bytes > max_unverified_path_bytes
        ):
            unverified_paths_truncated = True
            return
        unverified.append({"path": relative, "reason": reason})
        unverified_path_bytes += path_bytes

    while pending and not entries_truncated:
        directory = pending.pop()
        remaining = max_entries - entries_seen
        if remaining <= 0:
            entries_truncated = True
            unverified_paths_truncated = True
            record_unverified(directory, "directory-entry-budget", directory=True)
            break
        try:
            entries, directory_truncated = _bounded_directory_entries(directory, remaining)
        except OSError:
            record_unverified(directory, "directory-unreadable", directory=True)
            continue
        entries_seen += len(entries)
        if directory_truncated:
            entries_truncated = True
            unverified_paths_truncated = True
            record_unverified(directory, "directory-entry-budget", directory=True)
        directories: List[Path] = []
        for entry in entries:
            path = Path(entry.path)
            try:
                relative_depth = len(path.relative_to(root).parts)
            except ValueError:
                continue
            if relative_depth > max_depth:
                depth_truncated = True
                record_unverified(path, "max-depth")
                continue
            try:
                if entry.is_symlink():
                    if is_within_root(path, root):
                        if len(files) < max_files:
                            files.append(path)
                        else:
                            files_truncated = True
                            record_unverified(path, "file-count-budget")
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name not in IGNORED_DIRS:
                        directories.append(path)
                elif entry.is_file(follow_symlinks=False):
                    if len(files) < max_files:
                        files.append(path)
                    else:
                        files_truncated = True
                        record_unverified(path, "file-count-budget")
            except OSError:
                record_unverified(path, "metadata-unreadable")
                continue
        pending.extend(sorted(directories, key=_directory_priority, reverse=True))
    if pending:
        entries_truncated = True
        unverified_paths_truncated = True
        for directory in pending:
            record_unverified(directory, "directory-entry-budget", directory=True)
    return _CollectionResult(
        files=sorted(files, key=lambda path: _relative_path(root, path)),
        entries_seen=entries_seen,
        entries_truncated=entries_truncated,
        files_truncated=files_truncated,
        depth_truncated=depth_truncated,
        unverified=sorted(
            unverified, key=lambda item: (item["path"], item["reason"])
        ),
        unverified_summary=dict(sorted(unverified_summary.items())),
        unverified_path_bytes=unverified_path_bytes,
        unverified_paths_truncated=unverified_paths_truncated,
        unverified_directories=sorted(set(unverified_directories)),
    )


def _body_result_for_unselected(path: Path) -> _BodyResult:
    classification = classify_path(path)
    if classification == "sensitive":
        return _BodyResult("", False, "skipped", False, 0, "sensitive-existence-only")
    if classification == "symlink":
        return _BodyResult("", False, "skipped", False, 0, "symlink")
    return _BodyResult("", False, "skipped", False, 0, "not-selected")


def _read_bounded_body(
    root: Path,
    path: Path,
    max_file_bytes: int,
    remaining_bytes: int,
    selected_paths: Optional[Set[Path]] = None,
) -> _BodyResult:
    if path.name not in SCANNED_NAMES and (
        selected_paths is None or path not in selected_paths
    ):
        return _body_result_for_unselected(path)
    if classify_path(path) != "file" or not is_within_root(path, root):
        return _body_result_for_unselected(path)
    if remaining_bytes <= 0:
        return _BodyResult("", False, "skipped", False, 0, "content-byte-budget")
    limit = min(max_file_bytes, remaining_bytes)
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            raw = stream.read(limit)
    except OSError:
        return _BodyResult("", False, "unverified", False, 0, "unreadable")
    truncated = size > len(raw)
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _BodyResult("", False, "unverified", truncated, len(raw), "invalid-utf8")
    return _BodyResult(
        content,
        True,
        "truncated" if truncated else "scanned",
        truncated,
        len(raw),
        "file-byte-budget" if truncated else None,
    )


def _git_command(
    root: Path,
    arguments: List[str],
    timeout_seconds: float = GIT_TIMEOUT_SECONDS,
) -> _GitCommandResult:
    with tempfile.TemporaryFile() as stdout:
        process = subprocess.Popen(
            arguments,
            cwd=str(root),
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        stdout.seek(0)
        raw_output = stdout.read(MAX_GIT_OUTPUT_BYTES + 1)
    truncated = len(raw_output) > MAX_GIT_OUTPUT_BYTES
    return _GitCommandResult(
        returncode=process.returncode,
        stdout=raw_output[:MAX_GIT_OUTPUT_BYTES].decode("utf-8", errors="replace"),
        truncated=truncated,
    )


def _bounded_lines(output: str, limit: int, byte_truncated: bool) -> Tuple[List[str], bool]:
    lines = output.splitlines()
    if byte_truncated and output and not output.endswith(("\n", "\r")):
        lines.pop()
    return sorted(lines[:limit]), byte_truncated or len(lines) > limit


def _git_evidence(root: Path, recent_commits: int) -> Dict[str, object]:
    unavailable: Dict[str, object] = {
        "available": False,
        "reason": "not-a-git-worktree-or-command-unavailable",
        "status": [],
        "status_truncated": False,
        "commits": [],
        "commits_truncated": False,
    }
    try:
        probe = _git_command(root, ["git", "rev-parse", "--is-inside-work-tree"])
    except (OSError, subprocess.TimeoutExpired):
        unavailable["reason"] = "git-probe-unverified"
        return unavailable
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return unavailable

    requested_commit_count = max(0, recent_commits)
    log_limit = min(requested_commit_count, MAX_GIT_COMMIT_RECORDS + 1)
    try:
        status = _git_command(root, ["git", "status", "--short"])
        log = _git_command(
            root,
            ["git", "log", "-n", str(log_limit), "--format=%H%x1f%s"],
        )
    except (OSError, subprocess.TimeoutExpired):
        unavailable["reason"] = "git-evidence-timeout-or-unavailable"
        return unavailable

    commits: List[Dict[str, str]] = []
    commit_lines = log.stdout.splitlines()
    if log.truncated and log.stdout and not log.stdout.endswith(("\n", "\r")):
        commit_lines.pop()
    if log.returncode == 0 or log.truncated:
        for line in commit_lines[:MAX_GIT_COMMIT_RECORDS]:
            commit_hash, separator, subject = line.partition("\x1f")
            if separator:
                commits.append({"hash": commit_hash, "subject": subject})
    status_records, status_truncated = _bounded_lines(
        status.stdout if status.returncode == 0 or status.truncated else "",
        MAX_GIT_STATUS_RECORDS,
        status.truncated,
    )
    return {
        "available": True,
        "reason": None,
        "status": status_records,
        "status_truncated": status_truncated,
        "commits": commits,
        "commits_truncated": log.truncated
        or len(commit_lines) > MAX_GIT_COMMIT_RECORDS,
    }


def scan_project(
    root: Path,
    max_depth: int = 4,
    recent_commits: int = 50,
    *,
    max_entries: int = MAX_DIRECTORY_ENTRIES,
    max_files: int = MAX_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_content_bytes: int = MAX_CONTENT_BYTES,
) -> Dict[str, object]:
    """Scan a local root without executing project code or reading secret bodies."""
    resolved_root = root.resolve(strict=False)
    if not resolved_root.is_dir():
        raise ValueError("root must be an existing directory")
    depth = max(0, int(max_depth))
    entry_budget = max(1, int(max_entries))
    file_budget = max(1, int(max_files))
    per_file_budget = max(1, int(max_file_bytes))
    content_budget = max(0, int(max_content_bytes))
    collection = _collect_files(
        resolved_root,
        depth,
        entry_budget,
        file_budget,
        content_budget,
    )
    rule_discovery = select_rule_discovery_candidates(
        resolved_root,
        collection.files,
    )
    candidate_by_path = {
        str(candidate["path"]): candidate
        for candidate in rule_discovery["candidates"]
    }
    selected_paths = {
        resolved_root / Path(*relative.split("/"))
        for relative in candidate_by_path
    }

    inventory: List[Dict[str, object]] = []
    scanned_contents: Dict[Path, str] = {}
    content_bytes_read = 0
    body_by_path: Dict[Path, _BodyResult] = {}
    for path in sorted(collection.files, key=lambda item: _read_priority(resolved_root, item)):
        body = _read_bounded_body(
            resolved_root,
            path,
            per_file_budget,
            max(0, content_budget - content_bytes_read),
            selected_paths,
        )
        content_bytes_read += body.bytes_read
        if body.content_scanned:
            scanned_contents[path] = body.content
        body_by_path[path] = body
    for path in collection.files:
        body = body_by_path[path]
        relative_path = _relative_path(resolved_root, path)
        inventory_record = {
                "path": relative_path,
                "classification": classify_path(path),
                "content_scanned": body.content_scanned,
                "content_status": body.status,
                "content_truncated": body.truncated,
                "content_bytes": body.bytes_read,
                "content_reason": body.reason,
            }
        inventory.append(inventory_record)
        candidate = candidate_by_path.get(relative_path)
        if candidate is not None:
            candidate["content_scanned"] = body.content_scanned
            candidate["content_status"] = body.status
            candidate["content_truncated"] = body.truncated
            candidate["content_reason"] = body.reason

    content_bytes_truncated = any(
        item["content_status"] in {"truncated", "skipped"}
        and item["content_reason"] in {"file-byte-budget", "content-byte-budget"}
        for item in inventory
    )
    complete = not (
        collection.entries_truncated
        or collection.files_truncated
        or collection.depth_truncated
        or collection.unverified
        or collection.unverified_paths_truncated
        or content_bytes_truncated
        or any(item["content_status"] == "unverified" for item in inventory)
    )
    stack_signals = detect_stack_signals(
        resolved_root, collection.files, scanned_contents
    )
    project_evidence = detect_project_evidence(
        resolved_root, collection.files, scanned_contents, stack_signals
    )
    project_evidence["development_conventions"] = (
        detect_development_convention_evidence(
            resolved_root, rule_discovery["candidates"], scanned_contents
        )
    )
    if not complete:
        project_evidence["development_conventions"]["recovery_targets"] = (
            detect_convention_recovery_targets(
                resolved_root, collection.files, rule_discovery["candidates"]
            )
        )
    return {
        "root": str(resolved_root),
        "complete": complete,
        "files": inventory,
        "unverified": collection.unverified,
        "unverified_summary": collection.unverified_summary,
        "stack_signals": stack_signals,
        "project_evidence": project_evidence,
        "modules": detect_modules(
            resolved_root, collection.files, scanned_contents
        ),
        "rule_discovery": rule_discovery,
        "git": _git_evidence(resolved_root, int(recent_commits)),
        "limits": {
            "max_depth": depth,
            "max_directory_entries": entry_budget,
            "max_files": file_budget,
            "max_file_bytes": per_file_budget,
            "max_content_bytes": content_budget,
            "directory_entries_seen": collection.entries_seen,
            "directory_entries_truncated": collection.entries_truncated,
            "files_truncated": collection.files_truncated,
            "depth_truncated": collection.depth_truncated,
            "content_bytes_read": content_bytes_read,
            "content_bytes_truncated": content_bytes_truncated,
            "unverified_path_bytes": collection.unverified_path_bytes,
            "unverified_paths_truncated": collection.unverified_paths_truncated,
            "unverified_directories": collection.unverified_directories,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--recent-commits", type=int, default=50)
    parser.add_argument("--max-entries", type=int, default=MAX_DIRECTORY_ENTRIES)
    parser.add_argument("--max-files", type=int, default=MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_FILE_BYTES)
    parser.add_argument("--max-content-bytes", type=int, default=MAX_CONTENT_BYTES)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(
        json.dumps(
            scan_project(
                args.root,
                args.max_depth,
                args.recent_commits,
                max_entries=args.max_entries,
                max_files=args.max_files,
                max_file_bytes=args.max_file_bytes,
                max_content_bytes=args.max_content_bytes,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
