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


SENSITIVE_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}
IGNORED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv"}
SCANNED_NAMES = {"package.json", "pyproject.toml", "requirements.txt", "Pipfile", "manage.py"}
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
    for section in ("dependencies", "devDependencies", "peerDependencies"):
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
            for match in PYTHON_BACKEND_FRAMEWORK_PATTERN.findall(content):
                backend.add(match.lower())
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
                "stack_signals": detect_stack_signals(root, [path], contents),
            }
        )
    return sorted(modules, key=lambda module: str(module["path"]))


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
        pending.extend(reversed(directories))
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
) -> _BodyResult:
    if path.name not in SCANNED_NAMES:
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

    inventory: List[Dict[str, object]] = []
    scanned_contents: Dict[Path, str] = {}
    content_bytes_read = 0
    for path in collection.files:
        body = _read_bounded_body(
            resolved_root,
            path,
            per_file_budget,
            max(0, content_budget - content_bytes_read),
        )
        content_bytes_read += body.bytes_read
        if body.content_scanned:
            scanned_contents[path] = body.content
        inventory.append(
            {
                "path": _relative_path(resolved_root, path),
                "classification": classify_path(path),
                "content_scanned": body.content_scanned,
                "content_status": body.status,
                "content_truncated": body.truncated,
                "content_bytes": body.bytes_read,
                "content_reason": body.reason,
            }
        )

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
    return {
        "root": str(resolved_root),
        "complete": complete,
        "files": inventory,
        "unverified": collection.unverified,
        "unverified_summary": collection.unverified_summary,
        "stack_signals": detect_stack_signals(
            resolved_root, collection.files, scanned_contents
        ),
        "modules": detect_modules(
            resolved_root, collection.files, scanned_contents
        ),
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
