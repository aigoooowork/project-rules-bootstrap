import json
import tempfile
import unittest
from pathlib import Path

from scripts import render_adapters


ROOT = Path(__file__).resolve().parents[1]


class SimpleAdapterTests(unittest.TestCase):
    def load(self, path: Path) -> dict:
        function = getattr(render_adapters, "load_adapter_registry", None)
        if function is None:
            self.fail("render_adapters must own the simplified registry loader")
        return function(path)

    def test_bundled_registry_has_small_unique_per_tool_records(self) -> None:
        registry = self.load(ROOT / "references" / "adapters.json")
        records = registry["adapters"]

        self.assertEqual("2.0", registry["version"])
        self.assertEqual(
            {"codex", "claude-code", "cursor", "trae", "codebuddy", "workbuddy"},
            {record["id"] for record in records},
        )
        self.assertEqual(len(records), len({record["path"] for record in records}))
        for record in records:
            self.assertEqual(
                {"id", "name", "path", "support", "template"}, set(record)
            )
            self.assertNotIn("consumers", record)
            self.assertNotIn("shared_output", record)
            self.assertNotIn("sources", record)
            self.assertNotIn("verified_at", record)

    def test_rendered_adapters_route_only_to_the_canonical_index(self) -> None:
        registry = self.load(ROOT / "references" / "adapters.json")

        rendered, records, unknown = render_adapters.render_selected_adapters(
            ROOT, registry, ["codex", "workbuddy"]
        )

        self.assertEqual([], unknown)
        self.assertEqual({"codex", "workbuddy"}, {record["id"] for record in records})
        self.assertEqual({"AGENTS.md", "RULES.md"}, {item.path for item in rendered})
        for item in rendered:
            self.assertIn(".ai/rules/index.md", item.content)
            self.assertNotIn("adapter-id", item.content)
            self.assertNotIn("adapter-consumers", item.content)
            self.assertNotIn("## Scope", item.content)

    def test_unknown_selection_creates_no_output(self) -> None:
        registry = self.load(ROOT / "references" / "adapters.json")

        rendered, records, unknown = render_adapters.render_selected_adapters(
            ROOT, registry, ["unknown-tool"]
        )

        self.assertEqual([], rendered)
        self.assertEqual([], records)
        self.assertEqual(["unknown-tool"], unknown)

    def test_registry_rejects_duplicate_outputs_and_legacy_metadata(self) -> None:
        base = {
            "id": "one",
            "name": "One",
            "path": "AGENTS.md",
            "support": "native",
            "template": "assets/templates/adapters/agents.md",
        }
        cases = [
            {"version": "2.0", "adapters": [base, {**base, "id": "two"}]},
            {
                "version": "2.0",
                "adapters": [{**base, "consumers": ["one"]}],
            },
        ]
        for data in cases:
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "adapters.json"
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        self.load(path)


if __name__ == "__main__":
    unittest.main()
