import unittest


class UpdateRuleTests(unittest.TestCase):
    def test_unchanged_confirmed_canonical_constraint_does_not_require_reconfirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = {
            "id": "backend.repository-boundary",
            "type": "constraint",
            "status": "confirmed",
            "scope": "src/api/**",
            "text": "API handlers must not access the database directly.",
            "reason": "Keep persistence behind the repository boundary.",
            "exception_policy": "No exceptions.",
            "verification": "Inspect changed handlers.",
            "confirmation_id": "confirmation.backend.repository-boundary",
        }

        self.assertFalse(
            requires_constraint_confirmation(
                previous,
                dict(previous),
                already_canonical=True,
            )
        )

    def test_first_import_requires_confirmation_even_when_semantics_match(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        rule = {
            "id": "backend.repository-boundary",
            "type": "constraint",
            "status": "confirmed",
            "scope": "src/api/**",
            "text": "API handlers must not access the database directly.",
            "reason": "Keep persistence behind the repository boundary.",
            "exception_policy": "No exceptions.",
            "verification": "Inspect changed handlers.",
            "confirmation_id": "confirmation.backend.repository-boundary",
        }

        self.assertTrue(
            requires_constraint_confirmation(
                rule,
                dict(rule),
                already_canonical=False,
            )
        )

    def test_each_semantic_constraint_change_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = {
            "id": "backend.repository-boundary",
            "type": "constraint",
            "status": "confirmed",
            "scope": "src/api/**",
            "text": "API handlers must not access the database directly.",
            "reason": "Keep persistence behind the repository boundary.",
            "exception_policy": "No exceptions.",
            "verification": "Inspect changed handlers.",
            "confirmation_id": "confirmation.backend.repository-boundary",
        }
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
                        previous,
                        current,
                        already_canonical=True,
                    )
                )

    def test_changed_confirmation_state_or_identity_requires_confirmation(self) -> None:
        from scripts.update_rules import requires_constraint_confirmation

        previous = {
            "id": "backend.repository-boundary",
            "type": "constraint",
            "status": "confirmed",
            "scope": "src/api/**",
            "text": "API handlers must not access the database directly.",
            "reason": "Keep persistence behind the repository boundary.",
            "exception_policy": "No exceptions.",
            "verification": "Inspect changed handlers.",
            "confirmation_id": "confirmation.backend.repository-boundary",
        }
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
                        previous,
                        current,
                        already_canonical=True,
                    )
                )


if __name__ == "__main__":
    unittest.main()
