import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import write_outputs


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def manifest_content(files: dict, *, confirmations: list = None) -> str:
    records = []
    for path, (content, kind, adapter_id) in files.items():
        record = {"path": path, "sha256": digest(content), "kind": kind}
        if adapter_id is not None:
            record["adapter_id"] = adapter_id
        records.append(record)
    data = {
        "version": "2.0",
        "project": {"name": "integration", "language": "en"},
        "source": {"kind": "git", "revision": "abc123", "paths": ["."]},
        "files": records,
        "confirmations": confirmations or [],
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def writer_api(test: unittest.TestCase):
    planned_write = getattr(write_outputs, "PlannedWrite", None)
    apply_outputs = getattr(write_outputs, "apply_outputs", None)
    if planned_write is None or apply_outputs is None:
        test.fail("write_outputs must expose the single-plan v2 writer API")
    return planned_write, apply_outputs


class OutputWorkflowTests(unittest.TestCase):
    def test_initial_plan_creates_canonical_adapter_and_manifest(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        canonical = "# Rules\n"
        adapter = "Read `.ai/rules/index.md`.\n"
        files = {
            ".ai/rules/index.md": (canonical, "canonical", None),
            "AGENTS.md": (adapter, "adapter", "codex"),
        }
        manifest = manifest_content(files)
        writes = [
            PlannedWrite(".ai/rules/index.md", canonical, "create"),
            PlannedWrite(".ai/rules-manifest.json", manifest, "create"),
            PlannedWrite("AGENTS.md", adapter, "create"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            changed = apply_outputs(root, writes)

            self.assertEqual(
                [".ai/rules/index.md", "AGENTS.md", ".ai/rules-manifest.json"],
                changed,
            )
            self.assertEqual(canonical, (root / ".ai/rules/index.md").read_text())
            self.assertEqual(adapter, (root / "AGENTS.md").read_text())
            self.assertEqual(manifest, (root / ".ai/rules-manifest.json").read_text())

    def test_existing_unowned_file_is_never_overwritten(self) -> None:
        PlannedWrite, apply_outputs = writer_api(self)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "AGENTS.md"
            target.write_text("user content\n", encoding="utf-8")
            before = target.read_bytes()
            writes = [
                PlannedWrite("AGENTS.md", "generated\n", "create"),
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    manifest_content(
                        {"AGENTS.md": ("generated\n", "adapter", "codex")}
                    ),
                    "create",
                ),
            ]

            with self.assertRaises(FileExistsError):
                apply_outputs(root, writes)

            self.assertEqual(before, target.read_bytes())
            self.assertFalse((root / ".ai/rules-manifest.json").exists())

    def test_prior_manifest_authorizes_only_exact_owned_replacement(self) -> None:
        from scripts.manifest import validate_manifest_data
        PlannedWrite, apply_outputs = writer_api(self)

        old = "# Old rules\n"
        new = "# New rules\n"
        prior_text = manifest_content(
            {".ai/rules/index.md": (old, "canonical", None)}
        )
        prior = validate_manifest_data(json.loads(prior_text))
        new_manifest = manifest_content(
            {".ai/rules/index.md": (new, "canonical", None)}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai/rules").mkdir(parents=True)
            (root / ".ai/rules/index.md").write_text(old, encoding="utf-8")
            (root / ".ai/rules-manifest.json").write_text(prior_text, encoding="utf-8")
            writes = [
                PlannedWrite(
                    ".ai/rules/index.md", new, "replace-owned", digest(old)
                ),
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    new_manifest,
                    "replace-owned",
                    digest(prior_text),
                ),
            ]

            apply_outputs(root, writes, prior_manifest=prior)

            self.assertEqual(new, (root / ".ai/rules/index.md").read_text())
            self.assertEqual(
                new_manifest, (root / ".ai/rules-manifest.json").read_text()
            )

    def test_caller_cannot_forge_prior_ownership_for_an_unowned_file(self) -> None:
        from scripts.manifest import validate_manifest_data
        PlannedWrite, apply_outputs = writer_api(self)

        old = "user-owned\n"
        disk_manifest_text = manifest_content({})
        forged_manifest = validate_manifest_data(
            json.loads(
                manifest_content({"victim.md": (old, "canonical", None)})
            )
        )
        replacement = "generated\n"
        new_manifest = manifest_content(
            {"victim.md": (replacement, "canonical", None)}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai").mkdir()
            (root / ".ai/rules-manifest.json").write_text(
                disk_manifest_text, encoding="utf-8"
            )
            (root / "victim.md").write_text(old, encoding="utf-8")
            writes = [
                PlannedWrite("victim.md", replacement, "replace-owned", digest(old)),
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    new_manifest,
                    "replace-owned",
                    digest(disk_manifest_text),
                ),
            ]

            with self.assertRaisesRegex(ValueError, "on-disk prior manifest"):
                apply_outputs(root, writes, prior_manifest=forged_manifest)

            self.assertEqual(old, (root / "victim.md").read_text())
            self.assertEqual(
                disk_manifest_text,
                (root / ".ai/rules-manifest.json").read_text(),
            )

    def test_update_deletes_hash_guarded_retired_owned_output(self) -> None:
        from scripts.manifest import validate_manifest_data
        PlannedWrite, apply_outputs = writer_api(self)

        index = "# Index\n"
        retired = "# Retired\n"
        prior_text = manifest_content(
            {
                ".ai/rules/index.md": (index, "canonical", None),
                ".ai/rules/retired.md": (retired, "canonical", None),
            }
        )
        prior = validate_manifest_data(json.loads(prior_text))
        next_manifest = manifest_content(
            {".ai/rules/index.md": (index, "canonical", None)}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai/rules").mkdir(parents=True)
            (root / ".ai/rules/index.md").write_text(index, encoding="utf-8")
            (root / ".ai/rules/retired.md").write_text(retired, encoding="utf-8")
            (root / ".ai/rules-manifest.json").write_text(prior_text, encoding="utf-8")
            writes = [
                PlannedWrite(
                    ".ai/rules/retired.md", None, "delete-owned", digest(retired)
                ),
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    next_manifest,
                    "replace-owned",
                    digest(prior_text),
                ),
            ]

            changed = apply_outputs(root, writes, prior_manifest=prior)

            self.assertEqual(
                [".ai/rules/retired.md", ".ai/rules-manifest.json"], changed
            )
            self.assertFalse((root / ".ai/rules/retired.md").exists())
            self.assertEqual(
                next_manifest, (root / ".ai/rules-manifest.json").read_text()
            )

    def test_omitting_prior_owned_output_without_delete_is_rejected(self) -> None:
        from scripts.manifest import validate_manifest_data
        PlannedWrite, apply_outputs = writer_api(self)

        retired = "# Retired\n"
        prior_text = manifest_content(
            {".ai/rules/retired.md": (retired, "canonical", None)}
        )
        prior = validate_manifest_data(json.loads(prior_text))
        next_manifest = manifest_content({})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai/rules").mkdir(parents=True)
            (root / ".ai/rules/retired.md").write_text(retired, encoding="utf-8")
            (root / ".ai/rules-manifest.json").write_text(prior_text, encoding="utf-8")
            writes = [
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    next_manifest,
                    "replace-owned",
                    digest(prior_text),
                )
            ]

            with self.assertRaisesRegex(ValueError, "retired output requires"):
                apply_outputs(root, writes, prior_manifest=prior)

            self.assertTrue((root / ".ai/rules/retired.md").exists())

    def test_stale_owned_hash_rejects_the_whole_plan_before_writing(self) -> None:
        from scripts.manifest import validate_manifest_data
        PlannedWrite, apply_outputs = writer_api(self)

        old = "# Old rules\n"
        changed = "# User changed rules\n"
        prior_text = manifest_content(
            {".ai/rules/index.md": (old, "canonical", None)}
        )
        prior = validate_manifest_data(json.loads(prior_text))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".ai/rules").mkdir(parents=True)
            (root / ".ai/rules/index.md").write_text(changed, encoding="utf-8")
            (root / ".ai/rules-manifest.json").write_text(prior_text, encoding="utf-8")
            writes = [
                PlannedWrite(
                    ".ai/rules/index.md", "# New\n", "replace-owned", digest(old)
                ),
                PlannedWrite(
                    ".ai/rules-manifest.json",
                    manifest_content(
                        {".ai/rules/index.md": ("# New\n", "canonical", None)}
                    ),
                    "replace-owned",
                    digest(prior_text),
                ),
            ]

            with self.assertRaisesRegex(ValueError, "SHA-256"):
                apply_outputs(root, writes, prior_manifest=prior)

            self.assertEqual(changed, (root / ".ai/rules/index.md").read_text())
            self.assertEqual(prior_text, (root / ".ai/rules-manifest.json").read_text())

    def test_manifest_is_installed_after_every_other_output(self) -> None:
        import os
        PlannedWrite, apply_outputs = writer_api(self)

        canonical = "# Rules\n"
        manifest = manifest_content(
            {".ai/rules/index.md": (canonical, "canonical", None)}
        )
        writes = [
            PlannedWrite(".ai/rules-manifest.json", manifest, "create"),
            PlannedWrite(".ai/rules/index.md", canonical, "create"),
        ]
        calls = []
        real_replace = os.replace

        def record_replace(source, destination):
            calls.append(Path(destination).as_posix())
            return real_replace(source, destination)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("scripts.write_outputs.os.replace", side_effect=record_replace):
                apply_outputs(root, writes)

        self.assertTrue(calls[-1].endswith("/.ai/rules-manifest.json"))


if __name__ == "__main__":
    unittest.main()
