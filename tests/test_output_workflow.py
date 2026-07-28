import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict

from scripts.render_adapters import render_selected_adapters
from scripts.validate_outputs import load_adapter_registry, validate_output_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def tree_snapshot(root: Path) -> Dict[str, str]:
    snapshot = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def valid_manifest(adapters: list) -> Dict[str, object]:
    rule_id = "backend.repository-boundary"
    confirmation_id = "confirmation.backend.repository-boundary"
    return {
        "version": "1.0",
        "project": {"name": "integration", "language": "en"},
        "scan_baseline": {
            "kind": "full-scan",
            "captured_at": "2026-07-28T00:00:00Z",
            "paths": ["."],
            "fallback_reason": "integration fixture",
        },
        "rules": [
            {
                "id": rule_id,
                "domain": "backend",
                "type": "constraint",
                "status": "confirmed",
                "scope": "src/api/**",
                "text": "API handlers must not access the database directly.",
                "confidence": "high",
                "evidence": [
                    {
                        "kind": "user-confirmation",
                        "location": confirmation_id,
                        "observation": "The user explicitly confirmed the displayed constraint.",
                        "captured_at": "2026-07-28T00:01:00Z",
                    }
                ],
                "confirmation_id": confirmation_id,
                "reason": "Keep persistence behind the repository boundary.",
                "exception_policy": "No exceptions.",
                "verification": "Inspect changed handlers for direct database access.",
            }
        ],
        "adapters": adapters,
        "confirmations": [
            {
                "id": confirmation_id,
                "recorded_at": "2026-07-28T00:01:00Z",
                "decision": "confirmed",
                "scope": "src/api/**",
                "rule_ids": [rule_id],
            }
        ],
    }


class OutputWorkflowTests(unittest.TestCase):
    def test_two_gates_limit_real_file_changes_and_all_adapters_validate(self) -> None:
        from scripts.write_outputs import (
            MANAGED_END,
            MANAGED_START,
            PlannedWrite,
            apply_analysis,
            apply_final_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("owner documentation\n", encoding="utf-8")
            (root / "KEEP.md").write_text("never overwrite me\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "owner prefix\n{}\nold managed routing\n{}\nowner suffix\n".format(
                    MANAGED_START, MANAGED_END
                ),
                encoding="utf-8",
            )
            initial = tree_snapshot(root)

            self.assertEqual(
                [],
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "# Approved analysis\n",
                    approved=False,
                ),
            )
            self.assertEqual(initial, tree_snapshot(root))

            analysis_changes = apply_analysis(
                root,
                ".ai/rules.analysis.md",
                "# Approved analysis\n",
                approved=True,
            )
            self.assertEqual([".ai/rules.analysis.md"], analysis_changes)
            after_gate_one = tree_snapshot(root)
            self.assertEqual(
                {".ai/rules.analysis.md"},
                set(after_gate_one) - set(initial),
            )

            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            selected = [adapter["id"] for adapter in registry["adapters"]]
            rendered, manifest_adapters, unverified = render_selected_adapters(
                REPOSITORY_ROOT, registry, selected
            )
            self.assertEqual([], unverified)
            rule_content = (
                "# Integration backend\n\n"
                "## Scope\nsrc/api/**\n\n"
                "## Confirmed facts\n- The repository boundary was confirmed.\n\n"
                "## Confirmed constraints\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n\n"
                "## Execution rules\n- Keep database access behind repositories.\n\n"
                "## Verification\n- Inspect changed handlers for direct database access.\n\n"
                "## Related rules\n- None.\n"
            )
            manifest_content = json.dumps(
                valid_manifest(manifest_adapters),
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            writes = [
                PlannedWrite(".ai/rules/backend.md", rule_content, "create"),
                PlannedWrite(".ai/rules-manifest.json", manifest_content, "create"),
            ]
            for adapter in rendered:
                mode = "managed-block" if adapter.path == "AGENTS.md" else "create"
                writes.append(PlannedWrite(adapter.path, adapter.content, mode))
            approved_paths = [write.path for write in writes]

            self.assertEqual(
                [],
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=approved_paths,
                    approved=False,
                ),
            )
            self.assertEqual(after_gate_one, tree_snapshot(root))

            changed = apply_final_outputs(
                root,
                writes,
                approved_paths=approved_paths,
                approved=True,
            )

            self.assertEqual(sorted(approved_paths), changed)
            self.assertEqual("never overwrite me\n", (root / "KEEP.md").read_text(encoding="utf-8"))
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(agents.startswith("owner prefix\n"))
            self.assertTrue(agents.endswith("owner suffix\n"))
            self.assertNotIn("old managed routing", agents)
            self.assertEqual([], validate_output_tree(root, registry_path))

    def test_final_gate_preflight_never_overwrites_an_unowned_file(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "RULES.md").write_text("owner content\n", encoding="utf-8")
            before = tree_snapshot(root)
            writes = [
                PlannedWrite("RULES.md", "generated content\n", "create"),
                PlannedWrite(".ai/rules/project.md", "# Project\n", "create"),
            ]

            with self.assertRaises(FileExistsError):
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                )

            self.assertEqual(before, tree_snapshot(root))


if __name__ == "__main__":
    unittest.main()
