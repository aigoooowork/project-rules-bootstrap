"""Collect deterministic, read-only evidence about a local project."""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set


SENSITIVE_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}
IGNORED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv"}
MAX_GIT_OUTPUT_BYTES = 16 * 1024
MAX_GIT_STATUS_RECORDS = 200
MAX_GIT_COMMIT_RECORDS = 100


@dataclass(frozen=True)
class _GitCommandResult:
    returncode: int
    stdout: str
    truncated: bool


def classify_path(path: Path) -> str:
    """Return the scanner policy class for one filesystem path."""
    if path.name in SENSITIVE_NAMES:
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


def _package_dependencies(root: Path, path: Path) -> Set[str]:
    try:
        package = json.loads(_safe_text(root, path))
    except json.JSONDecodeError:
        return set()
    dependencies: Set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        values = package.get(section, {})
        if isinstance(values, dict):
            dependencies.update(str(name) for name in values)
    return dependencies


def detect_stack_signals(root: Path, files: List[Path]) -> Dict[str, List[str]]:
    """Identify direct framework signals without making architectural claims."""
    frontend: Set[str] = set()
    backend: Set[str] = set()
    for path in files:
        if not is_within_root(path, root) or classify_path(path) != "file":
            continue
        name = path.name
        if name == "package.json":
            dependencies = _package_dependencies(root, path)
            for framework in ("vue", "react", "angular", "svelte"):
                if framework in dependencies or "@angular/core" in dependencies and framework == "angular":
                    frontend.add(framework)
            for framework in ("express", "fastify", "nestjs"):
                dependency_name = "@nestjs/core" if framework == "nestjs" else framework
                if dependency_name in dependencies:
                    backend.add(framework)
        elif name == "pyproject.toml":
            backend.add("python")
        elif name in {"requirements.txt", "Pipfile", "manage.py"}:
            backend.add("python")
    return {"frontend": sorted(frontend), "backend": sorted(backend)}


def detect_modules(root: Path, files: List[Path]) -> List[Dict[str, object]]:
    """Return nested package/configuration roots as explicit module boundaries."""
    modules: List[Dict[str, object]] = []
    for path in files:
        if path.name not in {"package.json", "pyproject.toml"}:
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
                "stack_signals": detect_stack_signals(root, [path]),
            }
        )
    return sorted(modules, key=lambda module: str(module["path"]))


def _collect_files(root: Path, max_depth: int) -> List[Path]:
    files: List[Path] = []
    pending: List[Path] = [root]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            relative_depth = len(path.relative_to(root).parts)
            if relative_depth > max_depth:
                continue
            if entry.is_symlink():
                if is_within_root(path, root):
                    files.append(path)
            elif entry.is_dir(follow_symlinks=False):
                if entry.name not in IGNORED_DIRS:
                    pending.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
    return sorted(files, key=lambda path: _relative_path(root, path))


def _git_command(root: Path, arguments: List[str]) -> _GitCommandResult:
    process = subprocess.Popen(
        arguments,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    try:
        raw_output = process.stdout.read(MAX_GIT_OUTPUT_BYTES + 1)
        truncated = len(raw_output) > MAX_GIT_OUTPUT_BYTES
        if truncated:
            process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
    return _GitCommandResult(
        returncode=process.returncode,
        stdout=raw_output[:MAX_GIT_OUTPUT_BYTES].decode("utf-8", errors="replace"),
        truncated=truncated,
    )


def _bounded_lines(output: str, limit: int, byte_truncated: bool) -> tuple[List[str], bool]:
    lines = output.splitlines()
    if byte_truncated and output and not output.endswith(("\n", "\r")):
        lines.pop()
    return sorted(lines[:limit]), byte_truncated or len(lines) > limit


def _git_evidence(root: Path, recent_commits: int) -> Dict[str, object]:
    unavailable: Dict[str, object] = {
        "available": False,
        "status": [],
        "status_truncated": False,
        "commits": [],
        "commits_truncated": False,
    }
    try:
        probe = _git_command(root, ["git", "rev-parse", "--is-inside-work-tree"])
    except (OSError, subprocess.TimeoutExpired):
        return unavailable
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return unavailable

    requested_commit_count = max(0, recent_commits)
    commit_limit = min(requested_commit_count, MAX_GIT_COMMIT_RECORDS)
    try:
        status = _git_command(root, ["git", "status", "--short"])
        log = _git_command(
            root,
            ["git", "log", "-n", str(commit_limit), "--format=%H%x1f%s"],
        )
    except (OSError, subprocess.TimeoutExpired):
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
        "status": status_records,
        "status_truncated": status_truncated,
        "commits": commits,
        "commits_truncated": log.truncated
        or requested_commit_count > commit_limit
        or len(commit_lines) > MAX_GIT_COMMIT_RECORDS,
    }


def scan_project(root: Path, max_depth: int = 4, recent_commits: int = 50) -> Dict[str, object]:
    """Scan a local root without executing project code or reading secret bodies."""
    resolved_root = root.resolve(strict=False)
    if not resolved_root.is_dir():
        raise ValueError("root must be an existing directory")
    depth = max(0, int(max_depth))
    files = _collect_files(resolved_root, depth)
    scanned_names = {"package.json", "pyproject.toml", "requirements.txt", "Pipfile", "manage.py"}
    inventory = [
        {
            "path": _relative_path(resolved_root, path),
            "classification": classify_path(path),
            "content_scanned": classify_path(path) == "file" and path.name in scanned_names,
        }
        for path in files
    ]
    return {
        "root": str(resolved_root),
        "files": inventory,
        "stack_signals": detect_stack_signals(resolved_root, files),
        "modules": detect_modules(resolved_root, files),
        "git": _git_evidence(resolved_root, int(recent_commits)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--recent-commits", type=int, default=50)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(scan_project(args.root, args.max_depth, args.recent_commits), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
