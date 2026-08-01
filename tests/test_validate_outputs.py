import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.render_rules import render_rule_document, render_rule_index


ROOT = Path(__file__).resolve().parents[1]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def output_tree(root: Path, *, strong_outside: bool = False) -> None:
    (root / "src/api").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src/api/handler.py").write_text("def handle(): pass\n", encoding="utf-8")
    (root / "src/api/repository.py").write_text("def fetch(): pass\n", encoding="utf-8")
    (root / "tests/test_api.py").write_text("def test_handle(): pass\n", encoding="utf-8")
    constraint_text = "API handlers MUST use repositories."
    index = render_rule_index("Example", "en", ["backend"])
    rule = render_rule_document(
        "backend",
        "en",
        {
            "PROJECT_NAME": "Example",
            "SCOPE": "src/api/**",
            "CONFIRMED_FACTS": (
                "- `handle()` in `src/api/handler.py` calls `fetch()` in "
                "`src/api/repository.py`."
            ),
            "CONFIRMED_CONSTRAINTS": (
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- {}".format(constraint_text)
            ),
            "EXECUTION_RULES": (
                "- Handlers MUST call repositories."
                if strong_outside
                else (
                    "- Action: trace `handle()` → `fetch()` and extend the pair "
                    "covered by `tests/test_api.py`."
                )
            ),
            "VERIFICATION": "- Run `python -m unittest tests.test_api`.",
            "RELATED_RULES": "- [Index](index.md)",
        },
    )
    manifest = {
        "version": "2.0",
        "project": {"name": "Example", "language": "en"},
        "source": {"kind": "git", "revision": "abc123", "paths": ["."]},
        "files": [
            {
                "path": ".ai/rules/index.md",
                "sha256": digest(index),
                "kind": "canonical",
            },
            {
                "path": ".ai/rules/backend.md",
                "sha256": digest(rule),
                "kind": "canonical",
            },
        ],
        "confirmations": [
            {
                "id": "confirmation.backend.repository-boundary",
                "rule_id": "backend.repository-boundary",
                "scope": "src/api/**",
                "text_sha256": digest(constraint_text),
                "reason": "Preserve the repository boundary.",
                "exception_policy": "No exceptions.",
                "verification": "Inspect changed handlers.",
                "recorded_at": "2026-07-31T00:00:00Z",
            }
        ],
    }
    (root / ".ai/rules").mkdir(parents=True)
    (root / ".ai/rules/index.md").write_text(index, encoding="utf-8")
    (root / ".ai/rules/backend.md").write_text(rule, encoding="utf-8")
    (root / ".ai/rules-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class ValidateOutputTreeTests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module("scripts.validate_outputs")
        except Exception as error:
            self.fail("validate_outputs must use the simplified v2 modules: {}".format(error))

    def test_valid_dynamic_tree_has_no_issues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)

            issues = self.module().validate_output_tree(root)

        self.assertEqual([], issues)

    def test_hash_mismatch_and_symlink_are_reported_without_reading_outside(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            (root / ".ai/rules/backend.md").write_text("changed", encoding="utf-8")
            issues = self.module().validate_output_tree(root)
            self.assertIn("hash-mismatch", {issue.code for issue in issues})

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            outside = root / "outside.md"
            outside.write_text("secret canary", encoding="utf-8")
            target = root / ".ai/rules/backend.md"
            target.unlink()
            target.symlink_to(outside)
            issues = self.module().validate_output_tree(root)
            self.assertIn("unsafe-output", {issue.code for issue in issues})
            self.assertEqual("secret canary", outside.read_text())

    def test_persisted_analysis_and_strong_instruction_outside_confirmation_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root, strong_outside=True)
            (root / ".ai/rules.analysis.md").write_text("blind analysis", encoding="utf-8")

            issues = self.module().validate_output_tree(root)
            codes = {issue.code for issue in issues}

        self.assertIn("unexpected-analysis", codes)
        self.assertIn("unconfirmed-strong-instruction", codes)

    def test_descriptive_required_only_and_always_words_are_not_directives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            path = root / ".ai/rules/backend.md"
            text = path.read_text(encoding="utf-8").replace(
                "## Confirmed facts\n",
                "## Confirmed facts\n- The field is required.\n"
                "- This is a read-only endpoint.\n"
                "- The always-on service is external.\n",
            )
            path.write_text(text, encoding="utf-8")
            manifest_path = root / ".ai/rules-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][1]["sha256"] = digest(text)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            issues = self.module().validate_output_tree(root)

        self.assertNotIn("unconfirmed-strong-instruction", {issue.code for issue in issues})

    def test_constraint_marker_must_match_confirmation_text_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            manifest_path = root / ".ai/rules-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["confirmations"][0]["text_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            issues = self.module().validate_output_tree(root)

        self.assertIn("confirmation-text-mismatch", {issue.code for issue in issues})

    def test_generic_rule_without_real_chain_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            path = root / ".ai/rules/backend.md"
            generic = render_rule_document(
                "backend",
                "en",
                {
                    "PROJECT_NAME": "Example",
                    "SCOPE": "The backend.",
                    "CONFIRMED_FACTS": "- Python service with tests.",
                    "EXECUTION_RULES": "- Follow best practices and add tests.",
                    "VERIFICATION": "- Run the appropriate tests.",
                    "RELATED_RULES": "- [Index](index.md)",
                },
            )
            path.write_text(generic, encoding="utf-8")
            manifest_path = root / ".ai/rules-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][1]["sha256"] = digest(generic)
            manifest["confirmations"] = []
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            issues = self.module().validate_output_tree(root)

        self.assertIn("low-quality-rule", {issue.code for issue in issues})

    def test_unmarked_strong_item_in_constraint_section_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            path = root / ".ai/rules/backend.md"
            text = path.read_text(encoding="utf-8")
            text = text.replace(
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers MUST use repositories.",
                "- API handlers MUST use repositories.",
            )
            path.write_text(text, encoding="utf-8")
            manifest_path = root / ".ai/rules-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][1]["sha256"] = digest(text)
            manifest["confirmations"] = []
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            issues = self.module().validate_output_tree(root)

        self.assertIn("unconfirmed-constraint", {issue.code for issue in issues})

    def test_cli_returns_zero_for_valid_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_tree(root)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_outputs.py"), str(root)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
