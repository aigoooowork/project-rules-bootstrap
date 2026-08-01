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
        "RULE_TYPE": "code-chain",
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
            "<!-- constraint-id: deployment.approval -->\n"
            "- 生产发布必须经过已确认的审批流程。"
        )
        rendered = self.render("deployment", "zh-CN", values(constraint))

        self.assertIn("## 已确认的强约束", rendered)
        self.assertEqual(1, rendered.count("<!-- constraint-id: deployment.approval -->"))
        self.assertIn("生产发布必须", rendered)

    def test_accepts_extended_strong_constraint_language(self) -> None:
        for text in (
            "生产发布不得跳过审批。",
            "Production releases SHALL use the reviewed path.",
            "Only approved migrations are allowed.",
            "任何情况下都不能读取生产密钥。",
        ):
            with self.subTest(text=text):
                constraint = (
                    "<!-- constraint-id: deployment.extended -->\n- {}".format(text)
                )
                rendered = self.render(
                    "deployment", "zh-CN" if "。" in text else "en", values(constraint)
                )
                self.assertIn(text, rendered)

        semantic = (
            "<!-- constraint-id: deployment.semantic -->\n"
            "- Obtain security approval before deployment."
        )
        self.assertIn(
            "Obtain security approval",
            self.render("deployment", "en", values(semantic)),
        )

    def test_renders_explicit_rule_type_and_rejects_unknown_type(self) -> None:
        data = values()
        data["RULE_TYPE"] = "tooling"
        rendered = self.render("tooling", "en", data)
        self.assertIn("<!-- rule-type: tooling -->", rendered)

        data["RULE_TYPE"] = "convention"
        rendered = self.render("coding-conventions", "en", data)
        self.assertIn("<!-- rule-type: convention -->", rendered)

        data["RULE_TYPE"] = "generic"
        with self.assertRaisesRegex(ValueError, "RULE_TYPE"):
            self.render("tooling", "en", data)

    def test_rejects_unmarked_or_non_strong_confirmed_constraint_items(self) -> None:
        for constraints in (
            "- Code MUST pass validation.",
            "<!-- rule-id: deployment.legacy -->\n- Code MUST pass.",
            "<!-- constraint-id: deployment.approval -->\n- Code MUST pass.\n- Code NEVER skips.",
            (
                "<!-- constraint-id: deployment.approval -->\n- Code MUST pass.\n"
                "<!-- constraint-id: deployment.approval -->\n- Code NEVER skips."
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

    def test_index_can_record_compact_evidence_based_omissions(self) -> None:
        rendered = render_rules.render_rule_index(
            "Example",
            "en",
            ["deployment"],
            coverage_notes=[
                "tests — omitted: no project test exemplar was found",
                "generated-docs-and-artifacts — omitted: no generator boundary was found",
            ],
        )

        self.assertIn("## Development convention coverage", rendered)
        self.assertIn("- tests — omitted: no project test exemplar was found", rendered)
        self.assertIn("- generated-docs-and-artifacts — omitted:", rendered)
        self.assertNotIn("naming-and-case", rendered)

        default_rendered = self.index("Example", "en", ["deployment"])
        self.assertNotIn("Development convention coverage", default_rendered)

    def test_index_requires_at_least_one_domain(self) -> None:
        with self.assertRaises(ValueError):
            self.index("Example", "en", [])


if __name__ == "__main__":
    unittest.main()
