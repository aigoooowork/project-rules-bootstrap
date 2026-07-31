import json
import tempfile
import unittest
from pathlib import Path

from tests.test_output_workflow import manifest_content, writer_api


class SafeFilesystemTests(unittest.TestCase):
    def test_rejects_unsafe_or_sensitive_paths_before_writing(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        for unsafe in (
            "../outside.md",
            "/tmp/outside.md",
            "C:/outside.md",
            "nested\\outside.md",
            ".env",
            "config/secrets.json",
        ):
            with self.subTest(path=unsafe), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    apply_outputs(root, [PlannedWrite(unsafe, "x", "create")])
                self.assertEqual([], list(root.rglob("*")))

    def test_rejects_symlink_parent_or_target(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside"
            outside.mkdir()
            (root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                apply_outputs(root, [PlannedWrite("linked/rules.md", "x", "create")])
            self.assertFalse((outside / "rules.md").exists())

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.md"
            outside.write_text("outside", encoding="utf-8")
            (root / "AGENTS.md").symlink_to(outside)
            with self.assertRaises(ValueError):
                apply_outputs(root, [PlannedWrite("AGENTS.md", "x", "create")])
            self.assertEqual("outside", outside.read_text())

    def test_duplicate_targets_and_invalid_manifest_fail_without_staging_files(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = [
                PlannedWrite(".ai/rules/index.md", "one", "create"),
                PlannedWrite(".ai/rules/index.md", "two", "create"),
            ]
            with self.assertRaises(ValueError):
                apply_outputs(root, duplicate)
            self.assertEqual([], list(root.rglob("*")))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = "# Rules\n"
            mismatched_manifest = manifest_content(
                {".ai/rules/index.md": ("different", "canonical", None)}
            )
            writes = [
                PlannedWrite(".ai/rules/index.md", canonical, "create"),
                PlannedWrite(
                    ".ai/rules-manifest.json", mismatched_manifest, "create"
                ),
            ]
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                apply_outputs(root, writes)
            self.assertEqual([], list(root.rglob("*")))

    def test_manifest_content_must_be_valid_v2_json(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                apply_outputs(
                    root,
                    [
                        PlannedWrite(
                            ".ai/rules-manifest.json",
                            json.dumps({"version": "1.0"}),
                            "create",
                        )
                    ],
                )
            self.assertEqual([], list(root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
