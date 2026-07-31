import tempfile
import unittest
from pathlib import Path

from scripts.rule_quality import evaluate_rule_quality


class RuleQualityTests(unittest.TestCase):
    def test_accepts_project_anchored_complete_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "router.py").write_text("def dispatch(): pass\n")
            (root / "src" / "service.py").write_text("def execute(): pass\n")
            (root / "tests" / "test_router.py").write_text("def test_route(): pass\n")
            document = """# Example — request flow

## Scope
Request handling under `src/`.

## Confirmed facts
- `dispatch()` in `src/router.py` calls `execute()` in `src/service.py`.

## Execution rules
- Trace `dispatch()` → `execute()` and keep the public behavior covered by `tests/test_router.py`.

## Verification
- Run `pytest tests/test_router.py`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual([], result["issues"])
            self.assertEqual(3, result["existing_path_anchors"])
            self.assertGreaterEqual(result["symbol_anchors"], 2)
            self.assertEqual(1, result["chain_signals"])
            self.assertEqual(1, result["verification_commands"])

    def test_rejects_stack_inventory_without_actionable_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = """# Example — project

## Scope
The whole project.

## Confirmed facts
This is a Python FastAPI project with tests.

## Execution rules
Follow best practices and add tests for new code.

## Verification
Run the appropriate tests.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual(
                [
                    "missing-existing-project-anchors",
                    "missing-code-symbol-anchors",
                    "missing-complete-chain-signal",
                    "missing-verification-command",
                ],
                result["issues"],
            )

    def test_reports_invented_paths_as_missing_not_valid_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "real.py").write_text("def real(): pass\n")
            document = """# Example — flow

## Scope
`src/`

## Confirmed facts
`real()` in `src/real.py` calls `invented()` in `src/missing.py`.

## Execution rules
Trace `real()` → `invented()`.

## Verification
Run `pytest tests/missing.py`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual(1, result["existing_path_anchors"])
            self.assertEqual(
                ["src/missing.py", "tests/missing.py"],
                result["missing_path_anchors"],
            )
            self.assertIn("missing-existing-project-anchors", result["issues"])
            self.assertIn("invented-project-anchors", result["issues"])

    def test_counts_root_source_files_as_project_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "router.go").write_text("func route() {}\n")
            (root / "context.go").write_text("func next() {}\n")
            document = """# Example — routing

## Scope
Root package.

## Confirmed facts
`route()` in `router.go` calls `next()` in `context.go`.

## Execution rules
Trace `route()` → `next()`.

## Verification
Run `go test ./...`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual([], result["issues"])
            self.assertEqual(2, result["existing_path_anchors"])

    def test_dotted_symbols_are_not_treated_as_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "router.py").write_text("def add(): pass\n")
            (root / "handler.py").write_text("def run(): pass\n")
            document = """# Example — routing

## Scope
Root package.

## Confirmed facts
`Router.add()` in `router.py` creates `Route.run()` in `handler.py`.

## Execution rules
Trace `Router.add()` → `Route.run()`.

## Verification
Run `pytest tests`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual([], result["issues"])
            self.assertEqual([], result["missing_path_anchors"])

    def test_preserves_leading_dot_in_hidden_directory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "src").mkdir()
            (root / ".github/workflows/ci.yml").write_text("name: CI\n")
            (root / "src/main.py").write_text(
                "def main(): pass\ndef helper(): pass\n"
            )
            document = """# Example — automation

## Scope
CI entry point.

## Confirmed facts
`main()` and `helper()` live in `src/main.py`; CI is configured by `.github/workflows/ci.yml`.

## Execution rules
Trace `main()` → `helper()`.

## Verification
Run `python -m unittest tests`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertEqual([], result["issues"])
            self.assertEqual(2, result["existing_path_anchors"])

    def test_malformed_verification_command_is_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "router.py").write_text("def route(): pass\n")
            (root / "service.py").write_text("def run(): pass\n")
            document = """# Example — routing

## Scope
Root package.

## Confirmed facts
`route()` in `router.py` calls `run()` in `service.py`.

## Execution rules
Trace `route()` → `run()`.

## Verification
Run `pytest -k 'unterminated`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertIn("missing-verification-command", result["issues"])
            self.assertEqual(0, result["verification_commands"])

    def test_invented_symbols_and_plain_prose_do_not_satisfy_grounding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "router.py").write_text("def real_route(): pass\n")
            (root / "service.py").write_text("def real_service(): pass\n")
            document = """# Example — routing

## Scope
Root package.

## Confirmed facts
`TotallyFake()` in `router.py` calls `AlsoFake()` in `service.py`.

## Execution rules
Trace `TotallyFake()` → `AlsoFake()`.

## Verification
Use `these are ordinary words`.

## Related rules
None.
"""

            result = evaluate_rule_quality(root, document)

            self.assertIn("missing-code-symbol-anchors", result["issues"])
            self.assertIn("missing-complete-chain-signal", result["issues"])
            self.assertIn("missing-verification-command", result["issues"])
            self.assertEqual(0, result["symbol_anchors"])
            self.assertEqual(0, result["verification_commands"])


if __name__ == "__main__":
    unittest.main()
