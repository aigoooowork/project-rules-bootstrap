import hashlib
import json
import os
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


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def add_expected_hash(write: object, content: bytes) -> object:
    object.__setattr__(write, "expected_sha256", sha256_bytes(content))
    return write


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
    def test_existing_complete_output_tree_can_be_safely_updated_across_both_gates(self) -> None:
        from scripts.write_outputs import (
            MANAGED_END,
            MANAGED_START,
            PlannedWrite,
            apply_analysis,
            apply_final_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            rendered, manifest_adapters, unverified = render_selected_adapters(
                REPOSITORY_ROOT,
                registry,
                ["codex"],
            )
            self.assertEqual([], unverified)
            old_rule = (
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
            old_manifest = (
                json.dumps(valid_manifest(manifest_adapters), ensure_ascii=False, indent=2)
                + "\n"
            )
            old_analysis = b"# Prior approved analysis\r\n"
            old_agents = (
                b"\xef\xbb\xbfowner prefix\r\n"
                + MANAGED_START.encode("utf-8")
                + b"\r\n"
                + rendered[0].content.replace("\n", "\r\n").encode("utf-8")
                + b"\r\n"
                + MANAGED_END.encode("utf-8")
                + b"\r\nowner suffix\r\n"
            )
            (root / ".ai" / "rules").mkdir(parents=True)
            (root / ".ai" / "rules.analysis.md").write_bytes(old_analysis)
            (root / ".ai" / "rules" / "backend.md").write_text(
                old_rule,
                encoding="utf-8",
                newline="",
            )
            (root / ".ai" / "rules-manifest.json").write_text(
                old_manifest,
                encoding="utf-8",
                newline="",
            )
            (root / "AGENTS.md").write_bytes(old_agents)
            (root / "KEEP.bin").write_bytes(b"\x00unchanged\r\n")
            initial = tree_snapshot(root)

            try:
                analysis_changes = apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "# Updated approved analysis\n",
                    approved=True,
                    expected_sha256=sha256_bytes(old_analysis),
                )
            except (FileExistsError, TypeError) as error:
                self.fail("Gate 1 safe update is unavailable: {}".format(error))
            self.assertEqual([".ai/rules.analysis.md"], analysis_changes)
            after_gate_one = tree_snapshot(root)
            self.assertEqual(
                {".ai/rules.analysis.md"},
                {path for path in after_gate_one if after_gate_one[path] != initial[path]},
            )

            new_rule = old_rule.replace("# Integration backend", "# Updated backend")
            new_manifest = old_manifest.replace('"integration"', '"updated integration"')
            new_testing = (
                "# Testing\n\n"
                "## Scope\ntests/**\n\n"
                "## Confirmed facts\n- None.\n\n"
                "## Confirmed constraints\n\n"
                "## Execution rules\n- Run the documented test command.\n\n"
                "## Verification\n- Inspect the test result.\n\n"
                "## Related rules\n- None.\n"
            )
            writes = [
                add_expected_hash(
                    PlannedWrite(".ai/rules/backend.md", new_rule, "replace-owned"),
                    old_rule.encode("utf-8"),
                ),
                add_expected_hash(
                    PlannedWrite(
                        ".ai/rules-manifest.json",
                        new_manifest,
                        "replace-owned",
                    ),
                    old_manifest.encode("utf-8"),
                ),
                PlannedWrite(".ai/rules/testing.md", new_testing, "create"),
                add_expected_hash(
                    PlannedWrite("AGENTS.md", rendered[0].content + "\nupdated", "managed-block"),
                    old_agents,
                ),
            ]
            try:
                changed = apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                    prior_manifest_sha256=sha256_bytes(old_manifest.encode("utf-8")),
                    registry=registry_path,
                )
            except (FileExistsError, TypeError, ValueError) as error:
                self.fail("Gate 2 safe update is unavailable: {}".format(error))

            self.assertEqual(sorted(write.path for write in writes), changed)
            self.assertEqual(b"\x00unchanged\r\n", (root / "KEEP.bin").read_bytes())
            updated_agents = (root / "AGENTS.md").read_bytes()
            self.assertTrue(updated_agents.startswith(b"\xef\xbb\xbfowner prefix\r\n"))
            self.assertTrue(updated_agents.endswith(b"\r\nowner suffix\r\n"))
            self.assertNotEqual(initial[".ai/rules/backend.md"], tree_snapshot(root)[".ai/rules/backend.md"])
            self.assertEqual([], validate_output_tree(root, registry_path))

    def test_managed_block_update_preserves_every_byte_outside_the_markers(self) -> None:
        from scripts.write_outputs import MANAGED_END, MANAGED_START, PlannedWrite, apply_final_outputs

        cases = {
            "lf": (b"", b"\n"),
            "crlf": (b"", b"\r\n"),
            "bom-lf": (b"\xef\xbb\xbf", b"\n"),
            "bom-crlf": (b"\xef\xbb\xbf", b"\r\n"),
        }
        for name, (bom, newline) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                prefix = bom + b"owner prefix" + newline + MANAGED_START.encode("utf-8")
                suffix = MANAGED_END.encode("utf-8") + newline + b"owner suffix" + newline
                existing = prefix + newline + b"old managed body" + newline + suffix
                target = root / "AGENTS.md"
                target.write_bytes(existing)
                write = PlannedWrite("AGENTS.md", "new managed body", "managed-block")
                add_expected_hash(write, existing)

                apply_final_outputs(
                    root,
                    [write],
                    approved_paths=["AGENTS.md"],
                    approved=True,
                )

                updated = target.read_bytes()
                self.assertTrue(updated.startswith(prefix))
                self.assertTrue(updated.endswith(suffix))

    def test_gate_one_update_requires_exact_path_current_hash_and_regular_file(self) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".ai" / "rules.analysis.md"
            target.parent.mkdir()
            target.write_bytes(b"prior analysis\n")
            before = tree_snapshot(root)

            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    "rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(target.read_bytes()),
                )
            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256="0" * 64,
                )
            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_gate_one_rejects_analysis_symlink_before_reading_or_writing(self) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-analysis-target.md"
            outside.write_bytes(b"outside sentinel\n")
            link = root / ".ai" / "rules.analysis.md"
            link.parent.mkdir()
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest("symlink creation is unavailable: {}".format(error))

            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(outside.read_bytes()),
                )

            self.assertEqual(b"outside sentinel\n", outside.read_bytes())

    def test_gate_two_rejects_hash_mismatch_and_unowned_replacement_atomically(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rule_content = (
                "# Backend\n\n"
                "## Scope\nsrc/api/**\n\n"
                "## Confirmed facts\n- None.\n\n"
                "## Confirmed constraints\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n\n"
                "## Execution rules\n- Keep database access behind repositories.\n\n"
                "## Verification\n- Inspect changed handlers.\n\n"
                "## Related rules\n- None.\n"
            )
            manifest_content = json.dumps(
                valid_manifest([]),
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            (root / ".ai" / "rules").mkdir(parents=True)
            (root / ".ai" / "rules" / "backend.md").write_text(
                rule_content,
                encoding="utf-8",
                newline="",
            )
            (root / ".ai" / "rules-manifest.json").write_text(
                manifest_content,
                encoding="utf-8",
                newline="",
            )
            (root / "README.md").write_bytes(b"user-owned\n")
            before = tree_snapshot(root)
            prior_hash = sha256_bytes(manifest_content.encode("utf-8"))

            mismatch = PlannedWrite(
                ".ai/rules/backend.md",
                rule_content.replace("# Backend", "# Changed"),
                "replace-owned",
                "0" * 64,
            )
            with self.assertRaises(ValueError):
                apply_final_outputs(
                    root,
                    [mismatch],
                    approved_paths=[mismatch.path],
                    approved=True,
                    prior_manifest_sha256=prior_hash,
                )

            unowned = PlannedWrite(
                "README.md",
                "replacement\n",
                "replace-owned",
                sha256_bytes(b"user-owned\n"),
            )
            with self.assertRaises(ValueError):
                apply_final_outputs(
                    root,
                    [unowned],
                    approved_paths=[unowned.path],
                    approved=True,
                    prior_manifest_sha256=prior_hash,
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_managed_block_rejects_missing_duplicate_nested_or_reversed_markers(self) -> None:
        from scripts.write_outputs import MANAGED_END, MANAGED_START, PlannedWrite, apply_final_outputs

        cases = {
            "missing": b"owner content\n",
            "duplicate": (
                MANAGED_START
                + "\n"
                + MANAGED_START
                + "\nbody\n"
                + MANAGED_END
                + "\n"
            ).encode("utf-8"),
            "nested": (
                MANAGED_START
                + "\n"
                + MANAGED_START
                + "\nbody\n"
                + MANAGED_END
                + "\n"
                + MANAGED_END
            ).encode("utf-8"),
            "reversed": (MANAGED_END + "\nbody\n" + MANAGED_START).encode("utf-8"),
        }
        for name, existing in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "AGENTS.md"
                target.write_bytes(existing)
                write = PlannedWrite(
                    "AGENTS.md",
                    "replacement",
                    "managed-block",
                    sha256_bytes(existing),
                )

                with self.assertRaises(ValueError):
                    apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                    )

                self.assertEqual(existing, target.read_bytes())

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
                write = PlannedWrite(adapter.path, adapter.content, mode)
                if mode == "managed-block":
                    add_expected_hash(write, (root / adapter.path).read_bytes())
                writes.append(write)
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

    @unittest.skipUnless(os.name == "nt", "case aliases are a Windows path concern")
    def test_final_gate_rejects_case_alias_paths_before_any_write(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writes = [
                PlannedWrite("NEW.md", "first\n", "create"),
                PlannedWrite("new.md", "second\n", "create"),
            ]

            try:
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                )
            except (FileExistsError, ValueError):
                pass

            self.assertEqual({}, tree_snapshot(root))


if __name__ == "__main__":
    unittest.main()
