import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IterationTwoContractTests(unittest.TestCase):
    def test_content_contract_requires_actionable_rule_recipes(self) -> None:
        contract = (ROOT / "references" / "rule-content-contract.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "scope",
            "action",
            "project anchor",
            "verification",
            "stack-only",
            "generic",
            "two comparable",
            "stable project pattern",
        ):
            self.assertIn(phrase, contract)

    def test_every_domain_template_requires_action_anchor_and_verification(self) -> None:
        templates = sorted((ROOT / "assets" / "templates" / "rules").glob("*.md"))
        self.assertTrue(templates)
        for template in templates:
            with self.subTest(template=template.name):
                text = template.read_text(encoding="utf-8").lower()
                for phrase in ("action", "project anchor", "verification", "generic"):
                    self.assertIn(phrase, text)

    def test_code_chain_discovery_is_cross_language_and_task_oriented(self) -> None:
        discovery = (ROOT / "references" / "code-chain-discovery.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "python",
            "javascript",
            "java",
            "go",
            "cli",
            "complete code chain",
            "where to place",
            "what to reuse",
            "how to verify",
        ):
            self.assertIn(phrase, discovery)

    def test_init_discovers_code_chains_before_rendering_rules(self) -> None:
        skill = (ROOT / "skills" / "project-rules-init" / "SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertLess(skill.index("complete code chains"), skill.index("content preview"))
        for phrase in (
            "read candidate bodies",
            "stable repeated patterns",
            "where to place",
            "what to reuse",
            "how to verify",
        ):
            self.assertIn(phrase, skill)

    def test_normal_flow_has_one_confirmation_and_no_role_or_language_question(self) -> None:
        policy = (ROOT / "references" / "confirmation-policy.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("one write confirmation", policy)
        self.assertIn("do not ask for the user's role", policy)
        self.assertIn("current conversation language", policy)
        self.assertIn("stable repeated project patterns", policy)
        self.assertIn("without confirmation", policy)
        self.assertNotIn("gate 1", policy)
        self.assertNotIn("gate 2", policy)

    def test_update_reports_semantic_delta_and_traces_affected_chain(self) -> None:
        workflow = (ROOT / "references" / "update-workflow.md").read_text(
            encoding="utf-8"
        ).lower()
        for classification in ("`added`", "`modified`", "`retired`", "`conflict`"):
            self.assertIn(classification, workflow)
        self.assertIn("semantic rule delta", workflow)
        self.assertIn("affected complete code chain", workflow)
        self.assertIn("preserve it without re-confirmation", workflow)
        self.assertIn("stable code pattern changed", workflow)

    def test_risk_escalation_is_limited_to_material_decisions(self) -> None:
        policy = (ROOT / "references" / "confirmation-policy.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "credible conflict",
            "security",
            "data correctness",
            "new strong constraint",
            "unsafe or unowned overwrite",
            "insufficient evidence",
        ):
            self.assertIn(phrase, policy)
        self.assertIn("do not escalate", policy)
        self.assertIn("generic best practice", policy)

    def test_evals_cover_content_first_init_and_update(self) -> None:
        evals = json.loads((ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))[
            "evals"
        ]
        self.assertEqual({item["id"] for item in evals}, {1, 2, 3, 4, 5})
        for item in evals:
            with self.subTest(eval_id=item["id"]):
                self.assertTrue(item["prompt"])
                self.assertTrue(item["files"])
                self.assertGreaterEqual(len(item["expectations"]), 3)

        expectations = "\n".join(
            expectation for item in evals for expectation in item["expectations"]
        ).lower()
        for phrase in (
            "actionable",
            "project anchor",
            "complete code chain",
            "one write confirmation",
            "without re-confirmation",
            "current conversation language",
        ):
            self.assertIn(phrase, expectations)


if __name__ == "__main__":
    unittest.main()
