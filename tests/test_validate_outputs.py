import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

from scripts.validate_outputs import validate_output_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SUPPORT_LEVELS = {
    "native-auto",
    "import-supported",
    "manual-reference",
    "unverified",
}


def write_rule(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_manifest(
    root: Path, rules: List[Dict[str, object]], adapters: Optional[List[Dict[str, object]]] = None
) -> None:
    path = root / ".ai" / "rules-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, object] = {"rules": rules}
    if adapters is not None:
        manifest["adapters"] = adapters
    path.write_text(json.dumps(manifest), encoding="utf-8")


def write_adapter_registry(path: Path, adapters: List[Dict[str, object]]) -> None:
    path.write_text(json.dumps({"adapters": adapters}), encoding="utf-8")


class ValidateOutputTreeTests(unittest.TestCase):
    def test_bundled_adapter_registry_entries_reference_valid_templates_and_support_metadata(self) -> None:
        registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))

        self.assertIsInstance(registry.get("adapters"), list)
        self.assertTrue(registry["adapters"])
        for adapter in registry["adapters"]:
            with self.subTest(adapter=adapter.get("id")):
                self.assertIn(adapter.get("support"), ADAPTER_SUPPORT_LEVELS)
                self.assertEqual(adapter.get("verified_at"), "2026-07-28")
                self.assertIsInstance(adapter.get("sources"), list)
                self.assertTrue(adapter["sources"])
                self.assertTrue(all(source.startswith("https://") for source in adapter["sources"]))
                template = adapter.get("template")
                self.assertIsInstance(template, str)
                self.assertTrue((REPOSITORY_ROOT / template).is_file())

    def test_rule_without_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_rule(root, ".ai/rules/backend.md", "# Backend\n\n## 执行规则\n- Use repositories.\n")

            issues = validate_output_tree(root)

            self.assertIn("missing-scope", {issue.code for issue in issues})

    def test_unconfirmed_constraint_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [
                    {
                        "id": "backend.repository-boundary",
                        "type": "constraint",
                        "status": "candidate",
                    }
                ],
            )
            write_rule(
                root,
                ".ai/rules/restrictions.md",
                "# Restrictions\n\n## 适用范围\nbackend/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not query the database.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("unconfirmed-constraint", {issue.code for issue in issues})

    def test_restriction_rule_id_missing_from_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/restrictions.md",
                "# Restrictions\n\n## 适用范围\nbackend/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not query the database.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("unconfirmed-constraint", {issue.code for issue in issues})

    def test_non_constraint_rule_id_in_restrictions_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [
                    {
                        "id": "backend.repository-boundary",
                        "type": "fact",
                        "status": "confirmed",
                    }
                ],
            )
            write_rule(
                root,
                ".ai/rules/restrictions.md",
                "# Restrictions\n\n## 适用范围\nbackend/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not query the database.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("unconfirmed-constraint", {issue.code for issue in issues})

    def test_rule_id_in_two_canonical_files_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nbackend/**\n\n"
                "<!-- rule-id: backend.repository-boundary -->\n- Use repositories.\n",
            )
            write_rule(
                root,
                ".ai/rules/database.md",
                "# Database\n\n## 适用范围\ndatabase/**\n\n"
                "<!-- rule-id: backend.repository-boundary -->\n- Keep migrations versioned.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("duplicate-rule-id", {issue.code for issue in issues})

    def test_adapter_syntax_in_canonical_rule_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nbackend/**\n\nalwaysApply: true\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("adapter-syntax-in-canonical-rule", {issue.code for issue in issues})

    def test_adapter_support_claim_must_match_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "adapters.json"
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "manual-reference",
                    }
                ],
            )
            write_adapter_registry(
                registry_path,
                [
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "manual-reference",
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")
            write_rule(
                root,
                "RULES.md",
                "---\nadapter-id: workbuddy\nadapter-support: native-auto\n---\n"
                "Read .ai/rules/project.md for the shared rules.\n",
            )

            issues = validate_output_tree(root, registry_path)

            self.assertIn("adapter-support-mismatch", {issue.code for issue in issues})

    def test_manifest_adapter_support_must_match_authoritative_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "adapters.json"
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "native-auto",
                    }
                ],
            )
            write_adapter_registry(
                registry_path,
                [
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "manual-reference",
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")

            issues = validate_output_tree(root, registry_path)

            self.assertIn("adapter-support-mismatch", {issue.code for issue in issues})

    def test_registry_object_is_accepted_as_authoritative_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "native-auto",
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")
            registry = {
                "adapters": [
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "manual-reference",
                    }
                ]
            }

            issues = validate_output_tree(root, registry)

            self.assertIn("adapter-support-mismatch", {issue.code for issue in issues})

    def test_adapter_that_copies_a_canonical_rule_body_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            canonical_body = (
                "# Backend\n\n## 适用范围\nbackend/**\n\n"
                "## 执行规则\n<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers delegate database access to repositories.\n"
            )
            write_rule(root, ".ai/rules/backend.md", canonical_body)
            write_rule(
                root,
                "AGENTS.md",
                "# Agent instructions\n\nUse the canonical rules:\n\n" + canonical_body,
            )

            issues = validate_output_tree(root)

            self.assertIn("adapter-content-duplication", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
