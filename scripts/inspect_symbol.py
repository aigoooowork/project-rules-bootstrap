"""Classify Python symbol definitions, imports, and uses without executing code."""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set


IGNORED_DIRS = {".git", ".worktrees", ".venv", "node_modules", "dist", "build", "__pycache__"}
SENSITIVE_NAMES = {"secrets.py", "source_win_env.py"}
SYMBOL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_FILES = 4000
MAX_FILE_BYTES = 512 * 1024


class _Locations(ast.NodeVisitor):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.definitions: Set[int] = set()
        self.imports: Set[int] = set()
        self.uses: Set[int] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == self.symbol:
            self.definitions.add(node.lineno)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == self.symbol:
            self.definitions.add(node.lineno)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id != self.symbol:
            return
        if isinstance(node.ctx, ast.Store):
            self.definitions.add(node.lineno)
        elif isinstance(node.ctx, ast.Load):
            self.uses.add(node.lineno)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == self.symbol and isinstance(node.ctx, ast.Load):
            self.uses.add(node.lineno)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            visible = alias.asname or alias.name.split(".", 1)[0]
            if visible == self.symbol:
                self.imports.add(node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == self.symbol or alias.asname == self.symbol:
                self.imports.add(node.lineno)


def inspect_symbol(root: Path, symbol: str) -> Dict[str, object]:
    resolved = root.resolve(strict=False)
    if not resolved.is_dir() or SYMBOL_PATTERN.fullmatch(symbol) is None:
        raise ValueError("root and symbol must be safe")
    result: Dict[str, object] = {"symbol": symbol, "definitions": [], "imports": [], "uses": [], "unverified": []}
    files_seen = 0
    for path in sorted(resolved.rglob("*.py")):
        if files_seen >= MAX_FILES:
            result["unverified"].append({"reason": "file-budget"})
            break
        if (
            path.is_symlink()
            or path.name in SENSITIVE_NAMES
            or any(part in IGNORED_DIRS for part in path.parts)
        ):
            continue
        try:
            path.resolve(strict=True).relative_to(resolved)
        except (OSError, ValueError):
            continue
        files_seen += 1
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                result["unverified"].append({"path": path.relative_to(resolved).as_posix(), "reason": "file-byte-budget"})
                continue
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):
            result["unverified"].append({"path": path.relative_to(resolved).as_posix(), "reason": "unreadable-or-invalid-python"})
            continue
        locations = _Locations(symbol)
        locations.visit(tree)
        relative = path.relative_to(resolved).as_posix()
        for kind in ("definitions", "imports", "uses"):
            for line in sorted(getattr(locations, kind)):
                result[kind].append({"path": relative, "line": line})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("symbol")
    arguments = parser.parse_args()
    try:
        payload = inspect_symbol(arguments.root, arguments.symbol)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
