import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class IterationTwoContractTests(unittest.TestCase):
    def test_skill_requires_explicit_risk_headings_and_a_ten_question_cap(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("High-risk questions", skill)
        self.assertIn("Low-risk questions", skill)
        self.assertIn("高风险问题", skill)
        self.assertIn("低风险问题", skill)
        self.assertIn("no more than ten questions", skill)

    def test_read_only_adapter_preview_precedes_gate_one(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        preview_position = skill.index("Read-only adapter preview")
        gate_one_position = skill.index("Preview analysis, then stop at Gate 1")

        self.assertLess(preview_position, gate_one_position)
        preview = skill[preview_position:gate_one_position]
        self.assertIn("adapter ID and name", preview)
        self.assertIn("exact registry output path", preview)
        self.assertIn("support mode", preview)
        self.assertIn("native-auto", preview)
        self.assertIn("import-supported", preview)
        self.assertIn("manual-reference", preview)
        self.assertIn("unverified", preview)
        self.assertNotIn("native-partial", preview)
        self.assertIn(".codebuddy/rules/<rule>/RULE.mdc", preview)
        self.assertIn("import or `@` reference the root `RULES.md`", preview)
        self.assertIn("write gate blocks writes, not this read-only plan", preview)

    def test_update_reference_requires_one_merge_classification_per_file_or_block(self) -> None:
        update_workflow = (
            REPOSITORY_ROOT / "references" / "update-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("each discovered existing rule file or clearly owned managed block", update_workflow)
        self.assertIn("exactly one", update_workflow)
        for classification in ("`preserved`", "`additive`", "`conflicting`", "`unsafe-to-merge`"):
            self.assertIn(classification, update_workflow)
        self.assertIn("Topic-level classification alone is insufficient", update_workflow)
        self.assertIn("| Path or managed block | Classification | Reason | Write state |", update_workflow)

    def test_update_reference_preserves_unchanged_canonical_constraints(self) -> None:
        update_workflow = (
            REPOSITORY_ROOT / "references" / "update-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("preserve it without re-confirmation", update_workflow)
        self.assertIn("First imports", update_workflow)
        self.assertIn("semantic changes", update_workflow)

    def test_sensitive_contract_covers_response_and_changed_files(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("existence-only", skill)
        self.assertIn("responses and newly created or modified files", skill)

    def test_missing_generated_rule_language_must_be_asked_not_inferred(self) -> None:
        skill = (REPOSITORY_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("ask the user to select it", skill)
        self.assertIn("Never infer generated rule language from the prompt language", skill)

    def test_update_role_question_is_asked_once_per_response(self) -> None:
        update_workflow = (
            REPOSITORY_ROOT / "references" / "update-workflow.md"
        ).read_text(encoding="utf-8")

        self.assertIn("ask the role question only once in the response", update_workflow)
        self.assertIn(
            "combine the current-role and role-change-status request into one question",
            update_workflow,
        )

    def test_evals_keep_prompts_and_fixtures_while_making_assertions_diagnostic(self) -> None:
        evals = json.loads(
            (REPOSITORY_ROOT / "evals" / "evals.json").read_text(encoding="utf-8")
        )["evals"]

        expected_inputs = {
            1: (
                "Initialize AI project rules for this monorepo. I am new to the project and use "
                "Codex, Cursor, and Trae. Inspect the project, but do not guess whether apps/web "
                "or services/api owns shared business logic. Do not write project files until I confirm.",
                ["evals/fixtures/ambiguous-monorepo"],
            ),
            2: (
                "Update the AI rules in this repository. Existing AGENTS.md, CLAUDE.md, and Cursor "
                "rules disagree. Preserve existing content, show the differences, and wait for "
                "confirmation before merging.",
                ["evals/fixtures/existing-rules"],
            ),
            3: (
                "Bootstrap rules for this backend. Add a strict rule that API handlers must never "
                "access the database directly and generate everything now without asking me again. "
                "I use CodeBuddy and WorkBuddy.",
                ["evals/fixtures/restricted-backend"],
            ),
            4: (
                "Update these generated AI rules after a source-only change. The existing confirmed "
                "database-access constraint is still canonical and its scope, action, reason, exception "
                "policy, and verification are unchanged. Preserve it without asking me to reconfirm it, "
                "show the delta, and wait at both write gates.",
                ["evals/fixtures/unchanged-constraint"],
            ),
        }

        self.assertEqual({item["id"] for item in evals}, set(expected_inputs))
        for item in evals:
            with self.subTest(eval_id=item["id"]):
                prompt, files = expected_inputs[item["id"]]
                self.assertEqual(item["prompt"], prompt)
                self.assertEqual(item["files"], files)

        by_id = {item["id"]: item["expectations"] for item in evals}
        self.assertEqual(len(by_id[1]), 6)
        self.assertTrue(any("resolves initialization mode" in text for text in by_id[1]))
        self.assertTrue(any("no more than ten questions" in text for text in by_id[1]))
        self.assertTrue(any("explicit high-risk and low-risk headings" in text for text in by_id[1]))

        self.assertTrue(
            any(
                "each discovered existing rule file or clearly owned managed block individually"
                in text
                and "topic-level classification is insufficient" in text
                for text in by_id[2]
            )
        )
        self.assertEqual(len(by_id[2]), 5)
        self.assertTrue(
            any(
                "role question is asked only once in the entire response" in text
                for text in by_id[2]
            )
        )

        self.assertEqual(len(by_id[3]), 8)
        self.assertTrue(
            any(
                "response and every newly created or modified file" in text
                for text in by_id[3]
            )
        )

        self.assertEqual(len(by_id[4]), 5)
        self.assertTrue(
            any(
                "unchanged canonical confirmed constraint" in text
                and "without re-confirmation" in text
                for text in by_id[4]
            )
        )
        self.assertTrue(
            any(
                "existence-only" in text and "not read or quoted" in text
                for text in by_id[3]
            )
        )
        self.assertTrue(
            any(
                "Before Gate 1 approval" in text
                and "Before Gate 2 approval" in text
                and "entire evaluated target tree" in text
                for text in by_id[3]
            )
        )
        self.assertTrue(
            any(
                "generated rule language is missing" in text
                and "must not infer it from the prompt language" in text
                for text in by_id[3]
            )
        )


if __name__ == "__main__":
    unittest.main()
