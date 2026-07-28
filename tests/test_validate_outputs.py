import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

from scripts.render_adapters import render_adapter_template, render_selected_adapters
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


def evidence(kind: str = "source", location: str = "src/example.py") -> Dict[str, object]:
    return {
        "kind": kind,
        "location": location,
        "observation": "Observed test evidence.",
        "captured_at": "2026-07-28T00:00:00Z",
    }


def complete_rule(rule: Dict[str, object]) -> Dict[str, object]:
    rule_id = str(rule.get("id", "project.test-rule"))
    result: Dict[str, object] = {
        "id": rule_id,
        "domain": rule_id.split(".", 1)[0],
        "type": "fact",
        "status": "confirmed",
        "scope": "./",
        "text": "Observed test rule.",
        "confidence": "high",
        "evidence": [evidence()],
    }
    result.update(rule)
    if result["type"] == "constraint":
        result.setdefault("confirmation_id", "confirmation.{}".format(rule_id))
        result.setdefault("reason", "Protect the tested boundary.")
        result.setdefault("exception_policy", "No exceptions.")
        result.setdefault("verification", "Inspect the affected scope.")
    return result


def confirmed_constraint(
    rule_id: str = "backend.repository-boundary",
    scope: str = "src/api/**",
    confirmation_id: str = "confirmation.backend.repository-boundary",
) -> Dict[str, object]:
    return complete_rule(
        {
            "id": rule_id,
            "domain": rule_id.split(".", 1)[0],
            "type": "constraint",
            "status": "confirmed",
            "scope": scope,
            "text": "API handlers must not access the database directly.",
            "confirmation_id": confirmation_id,
            "evidence": [evidence("user-confirmation", confirmation_id)],
        }
    )


def confirmation(
    rule_id: str = "backend.repository-boundary",
    scope: str = "src/api/**",
    confirmation_id: str = "confirmation.backend.repository-boundary",
) -> Dict[str, object]:
    return {
        "id": confirmation_id,
        "recorded_at": "2026-07-28T00:01:00Z",
        "decision": "confirmed",
        "scope": scope,
        "rule_ids": [rule_id],
    }


def manifest_data(
    rules: List[Dict[str, object]],
    adapters: Optional[List[Dict[str, object]]] = None,
    confirmations: Optional[List[Dict[str, object]]] = None,
    language: str = "zh-CN",
) -> Dict[str, object]:
    complete_adapters = []
    for adapter in adapters or []:
        adapter_id = str(adapter.get("id", "workbuddy"))
        complete_adapter: Dict[str, object] = {
            "id": adapter_id,
            "path": "RULES.md",
            "support": "manual-reference",
            "template": "assets/templates/adapters/test.md",
            "registry_version": "1.0",
            "scope_loading": "manual",
            "import_capability": "explicit-reference",
            "consumers": [adapter_id],
        }
        complete_adapter.update(adapter)
        complete_adapters.append(complete_adapter)
    return {
        "version": "1.0",
        "project": {"name": "test", "language": language},
        "scan_baseline": {
            "kind": "full-scan",
            "captured_at": "2026-07-28T00:00:00Z",
            "paths": ["."],
            "fallback_reason": "test fixture",
        },
        "rules": [complete_rule(rule) for rule in rules],
        "adapters": complete_adapters,
        "confirmations": confirmations or [],
    }


def write_manifest(
    root: Path,
    rules: List[Dict[str, object]],
    adapters: Optional[List[Dict[str, object]]] = None,
    confirmations: Optional[List[Dict[str, object]]] = None,
    language: str = "zh-CN",
) -> None:
    path = root / ".ai" / "rules-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            manifest_data(
                rules,
                adapters=adapters,
                confirmations=confirmations,
                language=language,
            )
        ),
        encoding="utf-8",
    )


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
    path.write_text(json.dumps({"version": "1.0", "adapters": complete}), encoding="utf-8")


class ValidateOutputTreeTests(unittest.TestCase):
    def test_documented_validator_cli_runs_directly_from_repository_root(self) -> None:
        fixture = REPOSITORY_ROOT / "evals" / "fixtures" / "unchanged-constraint"

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/validate_outputs.py",
                str(fixture),
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_manifest_schema_rejects_single_invalid_variable(self) -> None:
        base = manifest_data([], language="en")
        invalid_cases = {}

        extra_property = deepcopy(base)
        extra_property["unexpected"] = True
        invalid_cases["top-level-additional-property"] = extra_property

        missing_project_language = deepcopy(base)
        del missing_project_language["project"]["language"]
        invalid_cases["missing-required-property"] = missing_project_language

        invalid_language = deepcopy(base)
        invalid_language["project"]["language"] = "English"
        invalid_cases["language-enum"] = invalid_language

        invalid_date = deepcopy(base)
        invalid_date["scan_baseline"]["captured_at"] = "28 July 2026"
        invalid_cases["date-time-format"] = invalid_date

        empty_evidence = manifest_data([complete_rule({"id": "project.runtime"})], language="en")
        empty_evidence["rules"][0]["evidence"] = []
        invalid_cases["evidence-min-items"] = empty_evidence

        bad_rule_enum = manifest_data([complete_rule({"id": "project.runtime"})], language="en")
        bad_rule_enum["rules"][0]["type"] = "guidance"
        invalid_cases["rule-enum"] = bad_rule_enum

        rule_additional_property = manifest_data(
            [complete_rule({"id": "project.runtime"})], language="en"
        )
        rule_additional_property["rules"][0]["unexpected"] = True
        invalid_cases["rule-additional-property"] = rule_additional_property

        bad_evidence_kind = manifest_data(
            [complete_rule({"id": "project.runtime"})], language="en"
        )
        bad_evidence_kind["rules"][0]["evidence"][0]["kind"] = "guess"
        invalid_cases["evidence-enum"] = bad_evidence_kind

        confirmation_additional_property = manifest_data(
            [confirmed_constraint()],
            confirmations=[confirmation()],
            language="en",
        )
        confirmation_additional_property["confirmations"][0]["actor"] = "test user"
        invalid_cases["confirmation-additional-property"] = confirmation_additional_property

        duplicate_confirmations = manifest_data(
            [confirmed_constraint()],
            confirmations=[confirmation(), confirmation()],
            language="en",
        )
        invalid_cases["unique-confirmation-ids"] = duplicate_confirmations

        duplicate_rules = manifest_data(
            [
                complete_rule({"id": "project.runtime"}),
                complete_rule({"id": "project.runtime"}),
            ],
            language="en",
        )
        invalid_cases["unique-rule-ids"] = duplicate_rules

        shared_constraint_confirmation = manifest_data(
            [
                confirmed_constraint(),
                confirmed_constraint(
                    rule_id="backend.job-repository-boundary",
                    confirmation_id="confirmation.backend.repository-boundary",
                ),
            ],
            confirmations=[
                {
                    **confirmation(),
                    "rule_ids": [
                        "backend.repository-boundary",
                        "backend.job-repository-boundary",
                    ],
                    "batch_reason": "One explicitly scoped batch decision.",
                }
            ],
            language="en",
        )
        invalid_cases["unique-constraint-confirmation-ids"] = (
            shared_constraint_confirmation
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            for name, data in invalid_cases.items():
                with self.subTest(case=name):
                    manifest_path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        from scripts.validate_outputs import load_manifest

                        load_manifest(manifest_path)

    def test_constraint_in_any_canonical_file_requires_explicit_confirmation(self) -> None:
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
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nsrc/api/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("unconfirmed-constraint", {issue.code for issue in issues})

    def test_constraint_section_rejects_a_rule_without_an_explicit_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [confirmed_constraint()],
                confirmations=[confirmation()],
            )
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nsrc/api/**\n\n"
                "## 已确认的强约束\n"
                "- API handlers must not access the database directly.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("missing-constraint-marker", {issue.code for issue in issues})

    def test_constraint_section_rejects_unmarked_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nsrc/api/**\n\n"
                "## 已确认事实\n- None.\n\n"
                "## 已确认的强约束\n"
                "API handlers must not access the database directly.\n\n"
                "## 执行规则\n- None.\n\n"
                "## 验证方式\n- Inspect the output.\n\n"
                "## 相关规则\n- None.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("missing-constraint-marker", {issue.code for issue in issues})

    def test_confirmed_constraint_rejects_self_asserted_manifest_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [confirmed_constraint()])
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nsrc/api/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("missing-constraint-confirmation", {issue.code for issue in issues})

    def test_constraint_confirmation_id_and_scope_must_match(self) -> None:
        cases = {
            "wrong-id": confirmation(confirmation_id="confirmation.other"),
            "wrong-scope": confirmation(scope="src/jobs/**"),
        }
        expected_codes = {
            "wrong-id": "missing-constraint-confirmation",
            "wrong-scope": "constraint-confirmation-scope-mismatch",
        }
        for name, record in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_manifest(
                    root,
                    [confirmed_constraint()],
                    confirmations=[record],
                )
                write_rule(
                    root,
                    ".ai/rules/backend.md",
                    "# Backend\n\n## 适用范围\nsrc/api/**\n\n"
                    "## 已确认的强约束\n"
                    "<!-- rule-id: backend.repository-boundary -->\n"
                    "- API handlers must not access the database directly.\n",
                )

                issues = validate_output_tree(root)

                self.assertIn(expected_codes[name], {issue.code for issue in issues})

    def test_constraint_canonical_scope_must_match_manifest_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(
                root,
                [confirmed_constraint(scope="src/api/**")],
                confirmations=[confirmation(scope="src/api/**")],
            )
            write_rule(
                root,
                ".ai/rules/backend.md",
                "# Backend\n\n## 适用范围\nsrc/jobs/**\n\n"
                "## 已确认的强约束\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n",
            )

            issues = validate_output_tree(root)

            self.assertIn("rule-scope-mismatch", {issue.code for issue in issues})

    def test_manifest_adapter_must_match_every_authoritative_registry_field(self) -> None:
        fields = {
            "path": "OTHER.md",
            "template": "assets/templates/adapters/other.md",
            "registry_version": "0.9",
            "scope_loading": "glob",
            "import_capability": "native",
            "support": "native-auto",
        }
        expected_codes = {
            "path": "adapter-path-mismatch",
            "template": "adapter-template-mismatch",
            "registry_version": "adapter-version-mismatch",
            "scope_loading": "adapter-scope-mismatch",
            "import_capability": "adapter-loading-mismatch",
            "support": "adapter-support-mismatch",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            registry_path.parent.mkdir()
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
            base_adapter = {
                "id": "workbuddy",
                "path": "RULES.md",
                "support": "manual-reference",
                "template": "assets/templates/adapters/test.md",
                "registry_version": "1.0",
                "scope_loading": "manual",
                "import_capability": "explicit-reference",
                "consumers": ["workbuddy"],
            }
            for field, invalid_value in fields.items():
                with self.subTest(field=field):
                    adapter = dict(base_adapter)
                    adapter[field] = invalid_value
                    write_manifest(root, [], adapters=[adapter])
                    write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")

                    issues = validate_output_tree(root, registry_path)

                    self.assertIn(expected_codes[field], {issue.code for issue in issues})

    def test_manifest_adapter_path_cannot_escape_or_name_sensitive_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            registry_path.parent.mkdir()
            write_adapter_registry(
                registry_path,
                [{"id": "workbuddy", "path": "RULES.md"}],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")
            for claimed_path in ("../RULES.md", "C:/temp/RULES.md", ".env"):
                with self.subTest(path=claimed_path):
                    write_manifest(
                        root,
                        [],
                        adapters=[
                            {
                                "id": "workbuddy",
                                "path": claimed_path,
                                "support": "manual-reference",
                                "template": "assets/templates/adapters/test.md",
                                "registry_version": "1.0",
                                "scope_loading": "manual",
                                "import_capability": "explicit-reference",
                                "consumers": ["workbuddy"],
                            }
                        ],
                    )

                    issues = validate_output_tree(root, registry_path)

                    self.assertIn("unsafe-adapter-path", {issue.code for issue in issues})

    def test_registry_authorized_adapter_symlink_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-adapter.txt"
            outside.write_text("OUTSIDE_ADAPTER_SENTINEL", encoding="utf-8")
            link = root / "AGENTS.md"
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest("symlink creation is unavailable: {}".format(error))
            registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")
            codex = next(adapter for adapter in registry["adapters"] if adapter["id"] == "codex")
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "codex",
                        "path": codex["path"],
                        "support": codex["support"],
                        "template": codex["template"],
                        "registry_version": registry["version"],
                        "scope_loading": codex["scope_loading"],
                        "import_capability": codex["import_capability"],
                        "consumers": ["codex"],
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")

            issues = validate_output_tree(root, REPOSITORY_ROOT / "references" / "adapters.json")

            self.assertIn("unsafe-adapter-path", {issue.code for issue in issues})

    def test_registry_rejects_unsafe_output_paths_and_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            registry_path.parent.mkdir()
            for output_path in ("../RULES.md", "C:/temp/RULES.md", ".env"):
                with self.subTest(path=output_path):
                    write_adapter_registry(
                        registry_path,
                        [{"id": "workbuddy", "path": output_path}],
                    )
                    with self.assertRaises(ValueError):
                        load_adapter_registry(registry_path)

            duplicate = authoritative_adapter(root, {"id": "workbuddy"})
            registry_path.write_text(
                json.dumps({"version": "1.0", "adapters": [duplicate, duplicate]}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_adapter_registry(registry_path)

    def test_manifest_and_registry_reject_unsafe_template_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            registry_path.parent.mkdir()
            write_adapter_registry(
                registry_path,
                [{"id": "workbuddy", "path": "RULES.md"}],
            )
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "workbuddy",
                        "path": "RULES.md",
                        "support": "manual-reference",
                        "template": "../adapter.md",
                        "registry_version": "1.0",
                        "scope_loading": "manual",
                        "import_capability": "explicit-reference",
                        "consumers": ["workbuddy"],
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")

            issues = validate_output_tree(root, registry_path)

            self.assertIn("unsafe-adapter-template", {issue.code for issue in issues})

            unsafe_registry = authoritative_adapter(root, {"id": "workbuddy"})
            unsafe_registry["template"] = "../adapter.md"
            registry_path.write_text(
                json.dumps({"version": "1.0", "adapters": [unsafe_registry]}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_adapter_registry(registry_path)

    def test_shared_rules_output_requires_one_registry_authorized_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            records = {adapter["id"]: adapter for adapter in registry["adapters"]}
            adapters = []
            for adapter_id in ("workbuddy", "generic"):
                adapter = records[adapter_id]
                adapters.append(
                    {
                        "id": adapter_id,
                        "path": adapter["path"],
                        "support": adapter["support"],
                        "template": adapter["template"],
                        "registry_version": registry["version"],
                        "scope_loading": adapter["scope_loading"],
                        "import_capability": adapter["import_capability"],
                        "consumers": [adapter_id],
                    }
                )
            write_manifest(root, [], adapters=adapters)
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")
            write_rule(root, "RULES.md", "# Rule navigation\n")

            issues = validate_output_tree(root, registry_path)

            self.assertIn("adapter-output-collision", {issue.code for issue in issues})

    def test_all_selection_resolves_shared_rules_output_once(self) -> None:
        from scripts.adapter_registry import resolve_adapter_selection

        registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")
        selected = [adapter["id"] for adapter in registry["adapters"]]

        resolved, unverified = resolve_adapter_selection(registry, selected)

        self.assertEqual([], unverified)
        self.assertEqual(6, len(resolved))
        rules_outputs = [adapter for adapter in resolved if adapter["path"] == "RULES.md"]
        self.assertEqual(1, len(rules_outputs))
        self.assertEqual("workbuddy", rules_outputs[0]["id"])
        self.assertEqual(["generic", "workbuddy"], rules_outputs[0]["consumers"])

    def test_all_selection_renders_six_unique_authorized_outputs(self) -> None:
        registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")
        selected = [adapter["id"] for adapter in registry["adapters"]]

        rendered, manifest_adapters, unverified = render_selected_adapters(
            REPOSITORY_ROOT, registry, selected
        )

        self.assertEqual([], unverified)
        self.assertEqual(6, len(rendered))
        self.assertEqual(6, len({item.path for item in rendered}))
        self.assertEqual(6, len(manifest_adapters))
        rules_manifest = next(item for item in manifest_adapters if item["path"] == "RULES.md")
        self.assertEqual(["generic", "workbuddy"], rules_manifest["consumers"])
        rules_output = next(item for item in rendered if item.path == "RULES.md")
        self.assertIn("adapter-id: workbuddy", rules_output.content)
        self.assertIn("adapter-consumers: generic,workbuddy", rules_output.content)

    def test_unverified_adapter_must_not_have_generated_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "references" / "adapters.json"
            registry_path.parent.mkdir()
            write_adapter_registry(
                registry_path,
                [
                    {
                        "id": "unknown-tool",
                        "path": "UNKNOWN.md",
                        "support": "unverified",
                    }
                ],
            )
            write_manifest(
                root,
                [],
                adapters=[
                    {
                        "id": "unknown-tool",
                        "path": "UNKNOWN.md",
                        "support": "unverified",
                        "template": "assets/templates/adapters/test.md",
                        "registry_version": "1.0",
                        "scope_loading": "manual",
                        "import_capability": "explicit-reference",
                        "consumers": ["unknown-tool"],
                    }
                ],
            )
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## 适用范围\n./\n")
            write_rule(
                root,
                "UNKNOWN.md",
                "<!-- adapter-id: unknown-tool -->\n"
                "<!-- adapter-support: unverified -->\n"
                "# Unknown\n",
            )

            issues = validate_output_tree(root, registry_path)

            self.assertIn("unverified-adapter-output", {issue.code for issue in issues})

    def test_manifest_language_controls_canonical_headings(self) -> None:
        cases = {
            "en": "# Project\n\n## 适用范围\n./\n",
            "zh-CN": "# Project\n\n## Scope\n./\n",
        }
        for language, wrong_heading in cases.items():
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_manifest(root, [], language=language)
                write_rule(root, ".ai/rules/project.md", wrong_heading)

                issues = validate_output_tree(root)

                self.assertIn("heading-language-mismatch", {issue.code for issue in issues})

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
                    registry_path.write_text(
                        json.dumps({"version": "1.0", "adapters": [adapter]}),
                        encoding="utf-8",
                    )
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
                if adapter["template"] == "assets/templates/adapters/rules.md":
                    self.assertNotIn("adapter-id:", content)
                    self.assertNotIn("adapter-support:", content)
                    self.assertNotIn("adapter-scope:", content)
                    self.assertNotIn("adapter-loading:", content)
                else:
                    self.assertEqual(metadata.get("adapter-id"), adapter["id"])
                    self.assertEqual(metadata.get("adapter-support"), adapter["support"])
                    self.assertIn("adapter-scope:", content)
                    self.assertIn("adapter-loading:", content)
                    self.assertEqual(metadata.get("adapter-consumers"), adapter["id"])

    def test_claude_adapter_uses_documented_plain_import_form(self) -> None:
        content = (
            REPOSITORY_ROOT / "assets" / "templates" / "adapters" / "claude.md"
        ).read_text(encoding="utf-8")

        self.assertIn("@.ai/rules/project.md", content)
        self.assertNotIn("`@.ai/rules/project.md`", content)

    def test_registry_uses_exact_shared_rules_template_mappings(self) -> None:
        registry = load_adapter_registry(REPOSITORY_ROOT / "references" / "adapters.json")
        templates = {adapter["id"]: adapter["template"] for adapter in registry["adapters"]}

        self.assertEqual(templates["workbuddy"], "assets/templates/adapters/rules.md")
        self.assertEqual(templates["generic"], "assets/templates/adapters/rules.md")
        self.assertFalse((REPOSITORY_ROOT / "assets/templates/adapters/generic-rules.md").exists())

    def test_shared_adapter_template_renders_selected_registry_identity(self) -> None:
        registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
        registry = load_adapter_registry(registry_path)
        selected = {
            adapter["id"]: adapter
            for adapter in registry["adapters"]
            if adapter["id"] in {"workbuddy", "generic"}
        }

        self.assertEqual(set(selected), {"workbuddy", "generic"})
        for adapter_id, adapter in selected.items():
            with self.subTest(adapter=adapter_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shared_template = REPOSITORY_ROOT / adapter["template"]
                rendered = render_adapter_template(shared_template, adapter)
                metadata = _adapter_metadata(rendered)
                self.assertEqual(metadata.get("adapter-id"), adapter_id)
                self.assertEqual(metadata.get("adapter-support"), adapter["support"])
                self.assertIn("adapter-scope: {}".format(adapter["scope_loading"]), rendered)
                self.assertIn("adapter-loading: {}".format(adapter["import_capability"]), rendered)
                self.assertNotIn("TEMPLATE METADATA", rendered)

                write_manifest(
                    root,
                    [],
                    adapters=[
                        {
                            "id": adapter_id,
                            "path": adapter["path"],
                            "support": adapter["support"],
                            "template": adapter["template"],
                            "registry_version": registry["version"],
                            "scope_loading": adapter["scope_loading"],
                            "import_capability": adapter["import_capability"],
                            "consumers": [adapter_id],
                        }
                    ],
                )
                write_rule(
                    root,
                    ".ai/rules/project.md",
                    "# Project\n\n## 适用范围\n./\n\n"
                    "## 已确认事实\n- None.\n\n"
                    "## 执行规则\n- None.\n\n"
                    "## 验证方式\n- Inspect the output.\n\n"
                    "## 相关规则\n- None.\n",
                )
                write_rule(root, adapter["path"], rendered)

                self.assertEqual(validate_output_tree(root, registry_path), [])

    def test_manifest_template_uses_schema_defined_pre_render_baseline_state(self) -> None:
        template = json.loads(
            (REPOSITORY_ROOT / "assets/templates/rules-manifest.json").read_text(encoding="utf-8")
        )
        schema_text = (REPOSITORY_ROOT / "references/output-schema.md").read_text(encoding="utf-8")

        self.assertIsNone(template["scan_baseline"])
        self.assertIn('"scan_baseline": {', schema_text)
        self.assertIn('"type": "object", "additionalProperties": false', schema_text)
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
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## Scope\n./\n")

            issues = validate_output_tree(root)

            self.assertIn("invalid-manifest", {issue.code for issue in issues})

    def test_rule_templates_use_language_tokens_and_renderer_removed_metadata(self) -> None:
        required_tokens = (
            "## {{SCOPE_HEADING}}",
            "## {{FACTS_HEADING}}",
            "## {{RULES_HEADING}}",
            "## {{VERIFICATION_HEADING}}",
            "## {{RELATED_HEADING}}",
        )
        rule_templates = sorted((REPOSITORY_ROOT / "assets" / "templates" / "rules").glob("*.md"))

        self.assertEqual(len(rule_templates), 10)
        for template in rule_templates:
            with self.subTest(template=template.name):
                content = template.read_text(encoding="utf-8")
                self.assertIn("renderer MUST remove", content)
                for token in required_tokens:
                    self.assertIn(token, content)
                self.assertIn("## {{CONSTRAINTS_HEADING}}", content)
                self.assertNotIn("适用范围 / Scope", content)
        restrictions = (REPOSITORY_ROOT / "assets" / "templates" / "rules" / "restrictions.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("otherwise omit the entire module", restrictions)

    def test_rule_renderer_emits_only_the_selected_language_headings(self) -> None:
        from scripts.render_rules import render_rule_template

        template = REPOSITORY_ROOT / "assets" / "templates" / "rules" / "project.md"
        values = {
            "PROJECT_NAME": "Example",
            "SCOPE": "./",
            "CONFIRMED_FACTS": "- Directly observed.",
            "CONFIRMED_CONSTRAINTS": "",
            "EXECUTION_RULES": "- Follow the observed rule.",
            "VERIFICATION": "- Inspect the result.",
            "RELATED_RULES": "- None.",
        }
        cases = {
            "en": ("## Scope", "## 适用范围"),
            "zh-CN": ("## 适用范围", "## Scope"),
        }
        for language, (expected, forbidden) in cases.items():
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                content = render_rule_template(template, language, values)
                write_manifest(root, [], language=language)
                write_rule(root, ".ai/rules/project.md", content)

                issues = validate_output_tree(root)

                self.assertIn(expected, content)
                self.assertNotIn(forbidden, content)
                self.assertNotIn("{{", content)
                self.assertEqual([], issues)

    def test_rule_without_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(root, ".ai/rules/backend.md", "# Backend\n\n## 执行规则\n- Use repositories.\n")

            issues = validate_output_tree(root)

            self.assertIn("missing-scope", {issue.code for issue in issues})

    def test_rule_without_other_required_heading_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [], language="en")
            write_rule(root, ".ai/rules/project.md", "# Project\n\n## Scope\n./\n")

            issues = validate_output_tree(root)

            self.assertIn("missing-heading", {issue.code for issue in issues})

    def test_chinese_canonical_scope_heading_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_manifest(root, [])
            write_rule(
                root,
                ".ai/rules/project.md",
                "# Project\n\n## 适用范围\n./\n",
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
                "version": "1.0",
                "adapters": [
                    authoritative_adapter(
                        root,
                        {
                            "id": "workbuddy",
                            "path": "RULES.md",
                            "support": "manual-reference",
                            "template": "assets/templates/adapters/test.md",
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
