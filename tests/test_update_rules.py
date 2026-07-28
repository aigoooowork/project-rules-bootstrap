import unittest


def constraint_rule() -> dict:
    return {
        "id": "backend.repository-boundary",
        "domain": "backend",
        "type": "constraint",
        "status": "confirmed",
        "scope": "src/api/**",
        "text": "API handlers must not access the database directly.",
        "confidence": "high",
        "evidence": [
            {
                "kind": "user-confirmation",
                "location": "confirmation.backend.repository-boundary",
                "observation": "The user confirmed the constraint.",
                "captured_at": "2026-07-28T00:01:00Z",
            }
        ],
        "reason": "Keep persistence behind the repository boundary.",
        "exception_policy": "No exceptions.",
        "verification": "Inspect changed handlers.",
        "confirmation_id": "confirmation.backend.repository-boundary",
    }


def prior_manifest(rule: dict, *, confirmations: object = None) -> dict:
    if confirmations is None:
        confirmations = [
            {
                "id": "confirmation.backend.repository-boundary",
                "recorded_at": "2026-07-28T00:01:00Z",
                "decision": "confirmed",
                "scope": "src/api/**",
                "rule_ids": ["backend.repository-boundary"],
            }
        ]
    return {
        "version": "1.0",
        "project": {"name": "update fixture", "language": "en"},
        "scan_baseline": {
            "kind": "full-scan",
            "captured_at": "2026-07-28T00:00:00Z",
            "paths": ["."],
            "fallback_reason": "test fixture",
        },
        "rules": [rule],
        "adapters": [],
        "confirmations": confirmations,
    }


class UpdateRuleTests(unittest.TestCase):
    def test_self_reported_canonical_state_without_confirmation_record_cannot_bypass(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        claimed_previous = constraint_rule()

        self.assertTrue(
            requires_constraint_confirmation(
                prior_manifest(claimed_previous, confirmations=[]),
                dict(claimed_previous),
            )
        )

    def test_unchanged_confirmed_canonical_constraint_does_not_require_reconfirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = constraint_rule()

        self.assertFalse(
            requires_constraint_confirmation(
                prior_manifest(previous),
                dict(previous),
            )
        )

    def test_first_import_requires_confirmation_even_when_semantics_match(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        rule = constraint_rule()

        self.assertTrue(
            requires_constraint_confirmation(
                None,
                dict(rule),
            )
        )

    def test_each_semantic_constraint_change_requires_confirmation(self) -> None:
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
                    requires_constraint_confirmation(
                        prior_manifest(previous),
                        current,
                    )
                )

    def test_changed_confirmation_state_or_identity_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = constraint_rule()
        changes = {
            "status": "candidate",
            "confirmation_id": "confirmation.replacement",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                current = dict(previous)
                current[field] = value
                self.assertTrue(
                    requires_constraint_confirmation(
                        prior_manifest(previous),
                        current,
                    )
                )

    def test_forged_prior_confirmation_decision_scope_or_reference_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = constraint_rule()
        base_record = prior_manifest(previous)["confirmations"][0]
        assert isinstance(base_record, dict)
        cases = {
            "decision": {**base_record, "decision": "deferred"},
            "scope": {**base_record, "scope": "src/jobs/**"},
            "reference": {**base_record, "rule_ids": ["backend.other-rule"]},
        }
        for name, record in cases.items():
            with self.subTest(case=name):
                self.assertTrue(
                    requires_constraint_confirmation(
                        prior_manifest(previous, confirmations=[record]),
                        dict(previous),
                    )
                )


if __name__ == "__main__":
    unittest.main()
