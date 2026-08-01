import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InspectSymbolTests(unittest.TestCase):
    def test_classifies_python_definition_import_and_use_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pkg").mkdir()
            (root / "pkg/source.py").write_text("_PING_INTERVAL = 15\n")
            (root / "pkg/consumer.py").write_text(
                "from pkg.source import _PING_INTERVAL\nprint(_PING_INTERVAL)\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/inspect_symbol.py"),
                    str(root),
                    "_PING_INTERVAL",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                [{"path": "pkg/source.py", "line": 1}], payload["definitions"]
            )
            self.assertEqual(
                [{"path": "pkg/consumer.py", "line": 1}], payload["imports"]
            )
            self.assertEqual(
                [{"path": "pkg/consumer.py", "line": 2}], payload["uses"]
            )

    def test_rejects_unsafe_symbol_and_never_reads_sensitive_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "secrets.py").write_text("TOKEN_SENTINEL = 1\n")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/inspect_symbol.py"), str(root), "../TOKEN"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertNotIn("TOKEN_SENTINEL", result.stdout + result.stderr)

    def test_does_not_follow_external_file_or_directory_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            outside = Path(outside_directory)
            (outside / "external.py").write_text("ESCAPE_SYMBOL = 1\n")
            try:
                (root / "linked.py").symlink_to(outside / "external.py")
                (root / "linked_dir").symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest("symlinks unavailable: {}".format(error))

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/inspect_symbol.py"), str(root), "ESCAPE_SYMBOL"],
                capture_output=True,
                text=True,
                check=False,
            )
            payload = json.loads(result.stdout)
            self.assertEqual([], payload["definitions"])
            self.assertNotIn("ESCAPE_SYMBOL", result.stderr)

    def test_dotted_import_reports_the_visible_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "consumer.py").write_text(
                "import pkg.mod\nimport other.mod as alias\nprint(pkg, alias)\n"
            )
            pkg = subprocess.run(
                [sys.executable, str(ROOT / "scripts/inspect_symbol.py"), str(root), "pkg"],
                capture_output=True,
                text=True,
                check=False,
            )
            alias = subprocess.run(
                [sys.executable, str(ROOT / "scripts/inspect_symbol.py"), str(root), "alias"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual([{"line": 1, "path": "consumer.py"}], json.loads(pkg.stdout)["imports"])
            self.assertEqual([{"line": 2, "path": "consumer.py"}], json.loads(alias.stdout)["imports"])


if __name__ == "__main__":
    unittest.main()
