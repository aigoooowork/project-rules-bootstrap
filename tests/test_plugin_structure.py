import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"missing YAML frontmatter: {path}")
    values = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


class PluginStructureTests(unittest.TestCase):
    def test_plugin_exposes_exactly_init_and_update_skills(self) -> None:
        manifest_path = ROOT / ".codex-plugin" / "plugin.json"
        plugin = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual("project-rules-bootstrap", plugin["name"])
        self.assertEqual("./skills/", plugin["skills"])

        skill_paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
        skill_names = {load_frontmatter(path)["name"] for path in skill_paths}
        self.assertEqual(
            {"project-rules-init", "project-rules-update"},
            skill_names,
        )
        self.assertFalse((ROOT / "SKILL.md").exists())

    def test_skills_have_distinct_triggers_and_share_the_core(self) -> None:
        init_path = ROOT / "skills" / "project-rules-init" / "SKILL.md"
        update_path = ROOT / "skills" / "project-rules-update" / "SKILL.md"
        init_text = init_path.read_text(encoding="utf-8")
        update_text = update_path.read_text(encoding="utf-8")
        init_frontmatter = load_frontmatter(init_path)
        update_frontmatter = load_frontmatter(update_path)

        self.assertIn("initial", init_frontmatter["description"].lower())
        self.assertNotIn("update", init_frontmatter["description"].lower())
        self.assertIn("update", update_frontmatter["description"].lower())
        self.assertIn("existing", update_frontmatter["description"].lower())

        for text in (init_text, update_text):
            self.assertIn("../../references/rule-content-contract.md", text)
            self.assertIn("../../references/adapters.json", text)
            self.assertIn("../../scripts/scan_project.py", text)
            self.assertNotIn('"adapters": [', text)


if __name__ == "__main__":
    unittest.main()
