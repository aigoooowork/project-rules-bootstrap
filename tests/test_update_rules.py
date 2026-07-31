import hashlib
import unittest


def text_hash(value: str) -> str:
    return hashlib.sha256(" ".join(value.split()).encode("utf-8")).hexdigest()


def constraint_rule() -> dict:
    return {
        "id": "backend.repository-boundary",
        "type": "constraint",
        "scope": "src/api/**",
        "text": "API handlers must not access the database directly.",
        "reason": "Keep persistence behind the repository boundary.",
        "exception_policy": "No exceptions.",
        "verification": "Inspect changed handlers.",
    }


def prior_manifest(rule: dict) -> dict:
    return {
        "version": "2.0",
        "project": {"name": "update fixture", "language": "en"},
        "source": {"kind": "git", "revision": "abc123", "paths": ["."]},
        "files": [],
        "confirmations": [
            {
                "id": "confirmation.backend.repository-boundary",
                "rule_id": rule["id"],
                "scope": rule["scope"],
                "text_sha256": text_hash(rule["text"]),
                "reason": rule["reason"],
                "exception_policy": rule["exception_policy"],
                "verification": rule["verification"],
                "recorded_at": "2026-07-31T00:00:00Z",
            }
        ],
    }


class UpdateRuleTests(unittest.TestCase):
    def test_unchanged_confirmed_constraint_does_not_require_reconfirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        rule = constraint_rule()

        self.assertFalse(requires_constraint_confirmation(prior_manifest(rule), rule))

    def test_missing_or_invalid_baseline_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        rule = constraint_rule()
        self.assertTrue(requires_constraint_confirmation(None, rule))
        self.assertTrue(requires_constraint_confirmation({"version": "1.0"}, rule))

    def test_each_semantic_change_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = constraint_rule()
        changes = {
            "scope": "src/**",
            "text": "No application code may access the database directly.",
            "reason": "A different reason.",
            "exception_policy": "Emergency exceptions require approval.",
            "verification": "Run an architecture check.",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                current = dict(previous)
                current[field] = value
                self.assertTrue(
                    requires_constraint_confirmation(prior_manifest(previous), current)
                )

    def test_non_constraint_or_incomplete_current_rule_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = constraint_rule()
        for change in ({"type": "fact"}, {"id": ""}, {"verification": ""}):
            current = {**previous, **change}
            with self.subTest(change=change):
                self.assertTrue(
                    requires_constraint_confirmation(prior_manifest(previous), current)
                )


if __name__ == "__main__":
    unittest.main()
