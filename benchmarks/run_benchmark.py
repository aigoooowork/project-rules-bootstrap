"""Reproduce bounded scan and grounding metrics for the pinned benchmark."""

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Mapping

from scripts.rule_quality import evaluate_rule_quality
from scripts.scan_project import scan_project


REPOSITORIES = {
    "pinia": "9db71974a2e3681d10a7f0247a17de5d44e27b1c",
    "react-hook-form": "8b5162173446e33648cf0d6ee28eb43a987c3af2",
    "fastapi": "95f8322ee1dcda7ceace7b1c4f6c9915b36d748f",
    "gin": "34dac209ffb6ef85cc78c5d217bbb7ad001d68fd",
    "spring-petclinic": "88e37c15cf6fc8490b01bc3e8e2c800cec1ac272",
}


def summarize_result(
    scan: Mapping[str, object],
    elapsed_ms: float,
    qualities: List[Mapping[str, object]],
) -> Dict[str, object]:
    """Reduce scanner and quality output to stable audit metrics."""
    limits = scan.get("limits", {})
    candidates = scan.get("rule_discovery", {}).get("candidates", [])
    active_limits = sorted(
        key
        for key, value in limits.items()
        if value is True and key.endswith("truncated")
    )
    candidate_symbols = sum(
        int(item.get("candidate_symbol_anchors", item["symbol_anchors"]))
        for item in qualities
    )
    verified_symbols = sum(int(item["symbol_anchors"]) for item in qualities)
    candidate_paths = {
        str(candidate.get("path")) for candidate in candidates
    }
    anchor_paths = {
        str(path)
        for item in qualities
        for path in item.get("existing_path_anchor_paths", [])
    }
    return {
        "elapsed_ms": round(elapsed_ms, 3),
        "scan_complete": bool(scan.get("complete", False)),
        "files_seen": len(scan.get("files", [])),
        "modules_detected": len(scan.get("modules", [])),
        "candidate_count": len(candidates),
        "candidate_modules": len(
            {str(candidate.get("module")) for candidate in candidates}
        ),
        "content_bytes_read": int(limits.get("content_bytes_read", 0)),
        "active_limits": active_limits,
        "rule_files": len(qualities),
        "grounded_rule_files": sum(1 for item in qualities if not item["issues"]),
        "existing_path_anchors": sum(
            int(item["existing_path_anchors"]) for item in qualities
        ),
        "candidate_symbol_anchors": candidate_symbols,
        "verified_symbol_anchors": verified_symbols,
        "scanner_anchor_coverage": (
            round(len(anchor_paths & candidate_paths) / len(anchor_paths), 3)
            if anchor_paths
            else 0.0
        ),
        "complete_chain_signals": sum(
            int(item["chain_signals"]) for item in qualities
        ),
        "verification_command_candidates": sum(
            int(item["verification_commands"]) for item in qualities
        ),
        "quality_issues": sorted(
            {str(issue) for item in qualities for issue in item["issues"]}
        ),
    }


def _head(path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(path),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def run(checkouts_root: Path, outputs_root: Path) -> Dict[str, object]:
    projects = {}
    for name, commit in REPOSITORIES.items():
        checkout = checkouts_root / name
        if _head(checkout) != commit:
            raise ValueError("{} checkout is not at pinned commit".format(name))
        started = time.perf_counter()
        scan = scan_project(
            checkout,
            max_depth=10,
            max_entries=30000,
            max_files=12000,
            max_file_bytes=64 * 1024,
            max_content_bytes=4 * 1024 * 1024,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        rule_root = outputs_root / name / ".ai/rules"
        rule_paths = sorted(
            path for path in rule_root.glob("*.md") if path.name != "index.md"
        )
        qualities = [
            evaluate_rule_quality(checkout, path.read_text(encoding="utf-8"))
            for path in rule_paths
        ]
        projects[name] = summarize_result(scan, elapsed_ms, qualities)
    return {
        "scanner_limits": {
            "max_depth": 10,
            "max_entries": 30000,
            "max_files": 12000,
            "max_file_bytes": 65536,
            "max_content_bytes": 4194304,
        },
        "projects": projects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkouts_root", type=Path)
    parser.add_argument("outputs_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.checkouts_root, args.outputs_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
