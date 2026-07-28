import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

from scripts.validate_outputs import _adapter_metadata, load_adapter_registry, validate_output_tree


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
    manifest: Dict[str, object] = {
        "version": "1.0",
        "project": {"name": "test", "language": "en"},
        "scan_baseline": {
            "kind": "full-scan",
            "captured_at": "2026-07-28T00:00:00Z",
            "paths": [],
            "fallback_reason": "test fixture",
        },
        "rules": rules,
        "confirmations": [],
    }
    if adapters is not None:
        manifest["adapters"] = adapters
    path.write_text(json.dumps(manifest), encoding="utf-8")


def authoritative_adapter(root: Path, adapter: Dict[str, object]) -> Dict[str, object]:
    """Build a complete registry entry for tests unrelated to registry validation."""
    template = adapter.get("template", "assets/templates/adapters/test.md")
    assert isinstance(template, str)
    template_path = Path(template)
    if not template_path.is_absolute():
        template_path = root / template_path
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("# adapter\n", encoding="utf-8")
    result: Dict[str, object] = {
        "id": "workbuddy",
        "name": "WorkBuddy",
        "path": "RULES.md",
        "scope_loading": "manual",
        "import_capability": "explicit-reference",
        "support": "manual-reference",
        "template": str(template_path) if Path(template).is_absolute() else template,
        "verified_at": "2026-07-28",
        "sources": ["https://example.test/rules"],
    }
    result.update(adapter)
    return result


def write_adapter_registry(path: Path, adapters: List[Dict[str, object]]) -> None:
    root = path.parent.parent if path.parent.name == "references" else path.parent
    complete = [authoritative_adapter(root, adapter) for adapter in adapters]
    path.write_text(json.dumps({"adapters": complete}), encoding="utf-8")


class ValidateOutputTreeTests(unittest.TestCase):
    def test_production_registry_loader_rejects_invalid_authoritative_adapter_metadata(self) -> None:
        base_adapter = {
            "id": "example",
            "name": "Example",
            "path": "RULES.md",
            "scope_loading": "manual",
            "import_capability": "explicit-reference",
            "support": "manual-reference",
            "template": "assets/templates/adapters/example.md",
            "verified_at": "2026-07-28",
            "sources": ["https://example.test/rules"],
        }
        cases = {
            "missing-name": {"name": None},
            "unsupported-support": {"support": "automatic"},
            "support-alias": {"support": None, "support_level": "manual-reference"},
            "duplicate-support-alias": {"support_level": "manual-reference"},
            "wrong-date": {"verified_at": "2026-07-27"},
            "non-https-source": {"sources": ["http://example.test/rules"]},
            "missing-template": {"template": "assets/templates/adapters/missing.md"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            write_rule(root, "assets/templates/adapters/example.md", "# adapter\n")
            registry_path.parent.mkdir()
            for name, changes in cases.items():
                with self.subTest(case=name):
                    adapter = dict(base_adapter)
                    adapter.update(changes)
                    registry_path.write_text(json.dumps({"adapters": [adapter]}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_adapter_registry(registry_path)

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

    def test_adapter_templates_declare_registry_id_support_scope_and_loading(self) -> None:
        registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")

        for adapter in registry["adapters"]:
            with self.subTest(adapter=adapter["id"]):
                content = (REPOSITORY_ROOT / adapter["template"]).read_text(encoding="utf-8")
                metadata = _adapter_metadata(content)
                if adapter["template"] != "assets/templates/adapters/rules.md":
                    self.assertEqual(metadata.get("adapter-id"), adapter["id"])
                else:
                    self.assertIn(metadata.get("adapter-id"), {"workbuddy", "generic"})
                self.assertEqual(metadata.get("adapter-support"), adapter["support"])
                self.assertIn("adapter-scope:", content)
                self.assertIn("adapter-loading:", content)

    def test_registry_uses_exact_shared_rules_template_mappings(self) -> None:
        registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")
        templates = {adapter["id"]: adapter["template"] for adapter in registry["adapters"]}

        self.assertEqual(templates["workbuddy"], "assets/templates/adapters/rules.md")
        self.assertEqual(templates["generic"], "assets/templates/adapters/rules.md")
        self.assertFalse((REPOSITORY_ROOT / "assets/templates/adapters/generic-rules.md").exists())

    def test_manifest_template_uses_schema_defined_pre_render_baseline_state(self) -> None:
        template = json.loads(
            (REPOSITORY_ROOT / "assets/templates/rules-manifest.json").read_text(encoding="utf-8")
        )
        schema_text = (REPOSITORY_ROOT / "references/output-schema.md").read_text(encoding="utf-8")

        self.assertIsNone(template["scan_baseline"])
        self.assertIn('"type": ["object", "null"]', schema_text)
        self.assertEqual(template["rules"], [])

    def test_final_manifest_rejects_uninitialized_scan_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "version": "1.0",
                "project": {"name": "test", "language": "en"},
                "scan_baseline": None,
                "rules": [],
                "adapters": [],
                "confirmations": [],
            }
            path = root / ".ai" / "rules-manifest.json"
            path.parent.mkdir()
            path.write_text(json.dumps(manifest), encoding="utf-8")
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围 / Scope\n./\n")

            issues = validate_output_tree(root)

            self.assertIn("invalid-manifest", {issue.code for issue in issues})

    def test_rule_templates_use_bilingual_headings_and_renderer_removed_metadata(self) -> None:
        required_headings = (
            "## 适用范围 / Scope",
            "## 已确认事实 / Confirmed facts",
            "## 执行规则 / Execution rules",
            "## 验证方式 / Verification",
            "## 相关规则 / Related rules",
        )
        rule_templates = sorted((REPOSITORY_ROOT / "assets" / "templates" / "rules").glob("*.md"))

        self.assertEqual(len(rule_templates), 10)
        for template in rule_templates:
            with self.subTest(template=template.name):
                content = template.read_text(encoding="utf-8")
                self.assertIn("renderer MUST remove", content)
                for heading in required_headings:
                    self.assertIn(heading, content)
                self.assertIn("## 已确认的强约束 / Confirmed constraints", content)
        restrictions = (REPOSITORY_ROOT / "assets" / "templates" / "rules" / "restrictions.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("otherwise omit the entire module", restrictions)

    def test_rule_without_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_rule(root, ".ai/rules/backend.md", "# Backend\n\n## 执行规则\n- Use repositories.\n")

            issues = validate_output_tree(root)

            self.assertIn("missing-scope", {issue.code for issue in issues})

    def test_bilingual_canonical_scope_heading_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/project.md",
                "# Project\n\n## 适用范围 / Scope\n./\n",
            )

            issues = validate_output_tree(root)

            self.assertNotIn("missing-scope", {issue.code for issue in issues})

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
                    authoritative_adapter(
                        root,
                        {
                            "id": "workbuddy",
                            "path": "RULES.md",
                            "support": "manual-reference",
                            "template": str(root / "adapter-template.md"),
                        },
                    )
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
