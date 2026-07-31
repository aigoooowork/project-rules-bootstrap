import unittest

from scripts import render_rules


def values(constraints: str = "") -> dict:
    return {
        "PROJECT_NAME": "Example",
        "SCOPE": "deploy/**",
        "CONFIRMED_FACTS": "- Deployments use the repository workflow.",
        "CONFIRMED_CONSTRAINTS": constraints,
        "EXECUTION_RULES": "- Action: extend `deploy/release.py` and copy its existing release path.",
        "VERIFICATION": "- Run `python -m unittest tests.test_release`.",
        "RELATED_RULES": "- [Testing](testing.md)",
    }


class DynamicRuleRenderingTests(unittest.TestCase):
    def render(self, domain: str, language: str, data: dict) -> str:
        function = getattr(render_rules, "render_rule_document", None)
        if function is None:
            self.fail("render_rule_document must replace fixed per-domain templates")
        return function(domain, language, data)

    def index(self, project: str, language: str, domains: list) -> str:
        function = getattr(render_rules, "render_rule_index", None)
        if function is None:
            self.fail("render_rule_index must provide the canonical entry file")
        return function(project, language, domains)

    def test_renders_domains_that_have_no_bundled_template(self) -> None:
        for domain in ("deployment", "observability", "message-queue"):
            with self.subTest(domain=domain):
                rendered = self.render(domain, "en", values())
                self.assertIn("# Example — {}".format(domain.replace("-", " ")), rendered)
                self.assertIn("## Scope", rendered)
                self.assertIn("Action:", rendered)
                self.assertIn("deploy/release.py", rendered)

    def test_selects_one_language_and_omits_empty_constraint_section(self) -> None:
        rendered = self.render("deployment", "zh-CN", values())

        self.assertIn("## 适用范围", rendered)
        self.assertIn("## 执行规则", rendered)
        self.assertNotIn("## Scope", rendered)
        self.assertNotIn("已确认的强约束", rendered)

    def test_includes_only_explicitly_confirmed_constraint_content(self) -> None:
        constraint = (
            "<!-- rule-id: deployment.approval -->\n"
            "- 生产发布必须经过已确认的审批流程。"
        )
        rendered = self.render("deployment", "zh-CN", values(constraint))

        self.assertIn("## 已确认的强约束", rendered)
        self.assertEqual(1, rendered.count("<!-- rule-id: deployment.approval -->"))
        self.assertIn("生产发布必须", rendered)

    def test_rejects_unmarked_or_non_strong_confirmed_constraint_items(self) -> None:
        for constraints in (
            "- Code MUST pass validation.",
            "<!-- rule-id: deployment.approval -->\n- Prefer validation.",
            "<!-- rule-id: deployment.approval -->\n- Code MUST pass.\n- Code NEVER skips.",
            (
                "<!-- rule-id: deployment.approval -->\n- Code MUST pass.\n"
                "<!-- rule-id: deployment.approval -->\n- Code NEVER skips."
            ),
        ):
            with self.subTest(constraints=constraints):
                with self.assertRaisesRegex(ValueError, "confirmed constraint"):
                    self.render("deployment", "en", values(constraints))

    def test_rejects_unsafe_domain_names_and_missing_actionable_fields(self) -> None:
        for domain in ("../outside", "Backend", "space name", ".env"):
            with self.subTest(domain=domain):
                with self.assertRaises(ValueError):
                    self.render(domain, "en", values())
        incomplete = values()
        incomplete["EXECUTION_RULES"] = ""
        with self.assertRaises(ValueError):
            self.render("deployment", "en", incomplete)

    def test_index_lists_only_actual_unique_domains(self) -> None:
        rendered = self.index(
            "Example", "en", ["deployment", "testing", "deployment"]
        )

        self.assertIn("# Example project rules", rendered)
        self.assertEqual(1, rendered.count("deployment.md"))
        self.assertEqual(1, rendered.count("testing.md"))
        self.assertNotIn("backend.md", rendered)

    def test_index_requires_at_least_one_domain(self) -> None:
        with self.assertRaises(ValueError):
            self.index("Example", "en", [])


if __name__ == "__main__":
    unittest.main()
