import importlib
import json
import tempfile
import unittest
from pathlib import Path


HASH_A = "a" * 64
HASH_B = "b" * 64


def valid_manifest() -> dict:
    return {
        "version": "2.0",
        "project": {"name": "example", "language": "zh-CN"},
        "source": {"kind": "git", "revision": "abc123", "paths": ["."]},
        "files": [
            {
                "path": ".ai/rules/backend.md",
                "sha256": HASH_A,
                "kind": "canonical",
            },
            {
                "path": "AGENTS.md",
                "sha256": HASH_B,
                "kind": "adapter",
                "adapter_id": "codex",
            },
        ],
        "confirmations": [
            {
                "id": "confirmation.backend.repository-boundary",
                "rule_id": "backend.repository-boundary",
                "scope": "src/api/**",
                "text_sha256": HASH_A,
                "reason": "Keep persistence behind repositories.",
                "exception_policy": "No exceptions.",
                "verification": "Inspect changed handlers.",
                "recorded_at": "2026-07-31T00:00:00Z",
            }
        ],
    }


class ManifestV2Tests(unittest.TestCase):
    def module(self):
        try:
            return importlib.import_module("scripts.manifest")
        except ModuleNotFoundError as error:
            self.fail("scripts.manifest must provide the simplified v2 contract: {}".format(error))

    def test_accepts_small_ownership_and_confirmation_manifest(self) -> None:
        manifest = self.module().validate_manifest_data(valid_manifest())

        self.assertEqual("2.0", manifest["version"])
        self.assertEqual(
            {
                ".ai/rules/backend.md": HASH_A,
                "AGENTS.md": HASH_B,
            },
            self.module().owned_file_hashes(manifest),
        )
        self.assertEqual(
            {"backend.repository-boundary"},
            set(self.module().confirmed_constraints(manifest)),
        )

    def test_load_manifest_reads_and_validates_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules-manifest.json"
            path.write_text(json.dumps(valid_manifest()), encoding="utf-8")

            loaded = self.module().load_manifest(path)

        self.assertEqual("example", loaded["project"]["name"])

    def test_rejects_legacy_content_ledgers_and_analysis_ownership(self) -> None:
        for field, value in (
            ("analysis_ownership", {"path": ".ai/rules.analysis.md"}),
            ("rules", []),
            ("adapters", []),
            ("scan_baseline", {}),
        ):
            with self.subTest(field=field):
                data = valid_manifest()
                data[field] = value
                with self.assertRaisesRegex(ValueError, "unexpected manifest field"):
                    self.module().validate_manifest_data(data)

    def test_rejects_unsafe_duplicate_or_invalid_owned_files(self) -> None:
        cases = {
            "parent traversal": [
                {"path": "../outside.md", "sha256": HASH_A, "kind": "canonical"}
            ],
            "absolute path": [
                {"path": "/tmp/outside.md", "sha256": HASH_A, "kind": "canonical"}
            ],
            "invalid hash": [
                {"path": ".ai/rules/a.md", "sha256": "bad", "kind": "canonical"}
            ],
            "duplicate path": [
                {"path": ".ai/rules/a.md", "sha256": HASH_A, "kind": "canonical"},
                {"path": ".ai/rules/a.md", "sha256": HASH_B, "kind": "canonical"},
            ],
            "adapter without id": [
                {"path": "AGENTS.md", "sha256": HASH_A, "kind": "adapter"}
            ],
        }
        for name, files in cases.items():
            with self.subTest(case=name):
                data = valid_manifest()
                data["files"] = files
                with self.assertRaises(ValueError):
                    self.module().validate_manifest_data(data)

    def test_rejects_incomplete_or_duplicate_confirmation_records(self) -> None:
        missing_hash = dict(valid_manifest()["confirmations"][0])
        missing_hash.pop("text_sha256")
        duplicate = dict(valid_manifest()["confirmations"][0])
        duplicate["id"] = "confirmation.duplicate-id"
        cases = ([missing_hash], [valid_manifest()["confirmations"][0], duplicate])
        for confirmations in cases:
            with self.subTest(confirmations=confirmations):
                data = valid_manifest()
                data["confirmations"] = confirmations
                with self.assertRaises(ValueError):
                    self.module().validate_manifest_data(data)

    def test_rejects_non_utc_or_malformed_confirmation_timestamps(self) -> None:
        for timestamp in (
            "yesterday",
            "2026-07-31",
            "2026-07-31T00:00:00+08:00",
            "2026-02-30T00:00:00Z",
        ):
            with self.subTest(timestamp=timestamp):
                data = valid_manifest()
                data["confirmations"][0]["recorded_at"] = timestamp
                with self.assertRaisesRegex(ValueError, "recorded_at"):
                    self.module().validate_manifest_data(data)


if __name__ == "__main__":
    unittest.main()
