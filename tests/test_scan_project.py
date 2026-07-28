import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.scan_project import scan_project


FIXTURES = Path(__file__).parent / "fixtures"


def copy_fixture(name: str, destination: Path) -> None:
    shutil.copytree(FIXTURES / name, destination, dirs_exist_ok=True)


def create_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        raise unittest.SkipTest("symlink creation is unavailable: {}".format(error))


class ScanProjectTests(unittest.TestCase):
    def test_scan_reports_frontend_stack_without_inventing_backend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_fixture("frontend-vue", root)

            result = scan_project(root)

            self.assertEqual(["vue"], result["stack_signals"]["frontend"])
            self.assertEqual([], result["stack_signals"]["backend"])

    def test_scan_keeps_monorepo_modules_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_fixture("monorepo", root)

            result = scan_project(root)

            self.assertEqual(
                ["apps/web", "services/api"],
                [module["path"] for module in result["modules"]],
            )

    def test_scan_reports_sensitive_path_without_reading_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("SECRET_SENTINEL=DO_NOT_COPY", encoding="utf-8")

            result = scan_project(root)
            record = next(item for item in result["files"] if item["path"] == ".env")

            self.assertIn(".env", json.dumps(result))
            self.assertNotIn("DO_NOT_COPY", json.dumps(result))
            self.assertEqual("sensitive", record.get("classification"))
            self.assertFalse(record["content_scanned"])

    def test_scan_does_not_follow_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-scan-fixture"
            outside.mkdir()
            (outside / "package.json").write_text(
                '{"dependencies": {"vue": "OUTSIDE_SENTINEL"}}', encoding="utf-8"
            )
            (outside / "pyproject.toml").write_text("[project]\nname = 'outside'\n", encoding="utf-8")
            link = root / "outside-link"
            self.addCleanup(lambda: shutil.rmtree(outside, ignore_errors=True))
            create_symlink_or_skip(link, outside)

            result = scan_project(root)

            self.assertNotIn("OUTSIDE_SENTINEL", json.dumps(result))
            self.assertNotIn("outside-link", [item["path"] for item in result["files"]])
            self.assertEqual({"frontend": [], "backend": []}, result["stack_signals"])
            self.assertEqual([], result["modules"])

    def test_scan_marks_non_git_directory_as_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = scan_project(Path(directory))

            self.assertFalse(result["git"]["available"])

    def test_scan_reports_bounded_newest_first_local_git_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.name", "Scanner Test")
            self._git(root, "config", "user.email", "scanner@example.invalid")
            self._git(root, "commit", "--allow-empty", "-m", "first commit")
            self._git(root, "commit", "--allow-empty", "-m", "second commit")
            self._git(root, "commit", "--allow-empty", "-m", "third commit")
            self._git(root, "commit", "--allow-empty", "-m", "fourth commit")

            result = scan_project(root, recent_commits=2)

            self.assertTrue(result["git"]["available"])
            self.assertEqual(
                ["fourth commit", "third commit"],
                [commit["subject"] for commit in result["git"]["commits"]],
            )

    def test_scan_bounds_git_status_records_and_marks_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.name", "Scanner Test")
            self._git(root, "config", "user.email", "scanner@example.invalid")
            self._git(root, "commit", "--allow-empty", "-m", "initial commit")
            for index in range(201):
                (root / "untracked-{:03}.txt".format(index)).write_text("x", encoding="utf-8")

            result = scan_project(root)

            self.assertEqual(200, len(result["git"]["status"]))
            self.assertTrue(result["git"].get("status_truncated"))

    @staticmethod
    def _git(root: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=str(root),
            check=True,
            capture_output=True,
            text=True,
        )
