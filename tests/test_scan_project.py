import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.scan_project import _git_command, scan_project, select_rule_discovery_candidates


FIXTURES = Path(__file__).parent / "fixtures"


def copy_fixture(name: str, destination: Path) -> None:
    shutil.copytree(FIXTURES / name, destination, dirs_exist_ok=True)


def create_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        raise unittest.SkipTest("symlink creation is unavailable: {}".format(error))


class ScanProjectTests(unittest.TestCase):
    def test_scan_extracts_declared_versions_commands_environment_and_specialties(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                """[project]
requires-python = ">=3.10"
dependencies = ["fastapi==0.115.0", "sqlalchemy>=2", "openai==1.2.3"]

[tool.poe.tasks]
test = "pytest tests -q"
""",
                encoding="utf-8",
            )
            (root / ".python-version").write_text("3.12.4\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
            (root / ".env.example").write_text("SECRET_SENTINEL=x\n", encoding="utf-8")

            result = scan_project(root, max_depth=4)
            evidence = result["project_evidence"]

            self.assertIn("api", evidence["specialized_discovery"])
            self.assertIn("database", evidence["specialized_discovery"])
            self.assertIn("ai", evidence["specialized_discovery"])
            self.assertTrue(any(item["runtime"] == "python" for item in evidence["runtime_declarations"]))
            self.assertTrue(any(item["command"] == "pytest tests -q" for item in evidence["command_candidates"]))
            self.assertTrue(any(item["path"] == ".env.example" for item in evidence["environment_sources"]))
            self.assertNotIn("SECRET_SENTINEL", json.dumps(result))

    def test_scan_reads_primary_source_before_docs_examples_under_tight_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs_src").mkdir()
            (root / "fastapi").mkdir()
            (root / "tests").mkdir()
            (root / "docs_src/example.py").write_text("EXAMPLE = 'x' * 400\n")
            (root / "fastapi/routing.py").write_text("def route_owner(): return 1\n")
            (root / "tests/test_routing.py").write_text("def test_route_owner(): pass\n")

            result = scan_project(root, max_depth=4, max_content_bytes=80)
            records = {item["path"]: item for item in result["files"]}

            self.assertTrue(records["fastapi/routing.py"]["content_scanned"])
            self.assertEqual(
                "primary-source",
                next(
                    item["scan_priority"]
                    for item in result["rule_discovery"]["candidates"]
                    if item["path"] == "fastapi/routing.py"
                ),
            )
            self.assertEqual(
                "docs-example",
                next(
                    item["scan_priority"]
                    for item in result["rule_discovery"]["candidates"]
                    if item["path"] == "docs_src/example.py"
                ),
            )

    def test_file_budget_traversal_reaches_primary_source_before_docs_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs/deep").mkdir(parents=True)
            (root / "fastapi").mkdir()
            for index in range(8):
                (root / "docs/deep/example_{}.py".format(index)).write_text("VALUE = 1\n")
            (root / "fastapi/routing.py").write_text("def route_owner(): return 1\n")

            result = scan_project(root, max_depth=5, max_files=2)
            paths = {item["path"] for item in result["files"]}

            self.assertIn("fastapi/routing.py", paths)

    def test_project_identity_separates_primary_framework_from_test_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "fastapi").mkdir()
            (root / "fastapi/__init__.py").write_text("__version__ = 'dev'\n")
            (root / "pyproject.toml").write_text(
                """[project]
name = "fastapi"
requires-python = ">=3.10"
dependencies = ["starlette>=0.46.0"]

[dependency-groups]
tests = ["flask>=3.0.0"]
""",
                encoding="utf-8",
            )

            result = scan_project(root, max_depth=4)

            self.assertEqual("fastapi", result["project_evidence"]["project_identity"]["name"])
            self.assertEqual(["fastapi"], result["project_evidence"]["primary_frameworks"])
            self.assertNotIn("flask", result["stack_signals"]["backend"])

    def test_candidate_fill_preserves_core_file_and_parent_diversity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "fastapi/routing.py", root / "fastapi/applications.py"]
            paths.extend(root / "fastapi/middleware/m{}.py".format(index) for index in range(8))
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("def value(): return 1\n")

            result = select_rule_discovery_candidates(
                root, paths, max_candidates_per_module=5
            )
            selected = [item["path"] for item in result["candidates"]]

            self.assertIn("fastapi/routing.py", selected)
            self.assertLessEqual(
                sum(path.startswith("fastapi/middleware/") for path in selected), 2
            )

    def test_docs_example_cannot_displace_primary_source_in_same_module(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "module/src/core.py", root / "module/docs/routes.py"]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("def value(): return 1\n")
            result = select_rule_discovery_candidates(root, paths, max_candidates_per_module=1)
            self.assertEqual("module/src/core.py", result["candidates"][0]["path"])

    def test_dev_only_ai_dependency_does_not_enable_ai_specialty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                json.dumps(
                    {
                        "packageManager": "pnpm@10.0.0",
                        "dependencies": {"express": "5.0.0"},
                        "devDependencies": {"openai": "2.0.0"},
                        "scripts": {"test": "vitest"},
                    }
                ),
                encoding="utf-8",
            )
            result = scan_project(root)
            evidence = result["project_evidence"]
            self.assertNotIn("ai", evidence["specialized_discovery"])
            self.assertIn("api", evidence["specialized_discovery"])
            self.assertTrue(any(item["scope"] == "development" for item in evidence["dependency_declarations"] if item["name"] == "openai"))
            self.assertTrue(any(item["command"] == "pnpm run test" for item in evidence["command_candidates"]))

    def test_dev_only_node_framework_does_not_enable_api_specialty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                json.dumps({"devDependencies": {"express": "5.0.0"}}),
                encoding="utf-8",
            )
            result = scan_project(root)
            self.assertNotIn("api", result["project_evidence"]["specialized_discovery"])

    def test_python_test_extra_does_not_enable_ai_specialty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname="demo"\n[project.optional-dependencies]\ntest=["openai>=1"]\n',
                encoding="utf-8",
            )
            result = scan_project(root)
            evidence = result["project_evidence"]
            self.assertNotIn("ai", evidence["specialized_discovery"])
            self.assertTrue(any(item["scope"] == "optional:test" for item in evidence["dependency_declarations"]))

    def test_go_and_java_runtime_dependencies_route_specialties(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "go.mod").write_text(
                "module example\nrequire github.com/gin-gonic/gin v1.10.0\n",
                encoding="utf-8",
            )
            (root / "pom.xml").write_text(
                """<project><dependencies>
<dependency><groupId>org.springframework</groupId><artifactId>spring-web</artifactId></dependency>
<dependency><groupId>org.hibernate.orm</groupId><artifactId>hibernate-core</artifactId></dependency>
</dependencies></project>""",
                encoding="utf-8",
            )
            result = scan_project(root)
            specialties = result["project_evidence"]["specialized_discovery"]
            self.assertIn("api", specialties)
            self.assertIn("database", specialties)

    def test_monorepo_commands_use_each_package_manager(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for package, manager in (("a", "pnpm@10"), ("b", "yarn@4")):
                package_root = root / "apps" / package
                package_root.mkdir(parents=True)
                (package_root / "package.json").write_text(
                    json.dumps({"packageManager": manager, "scripts": {"test": "vitest"}}),
                    encoding="utf-8",
                )
            result = scan_project(root)
            commands = {
                (item["source"], item["command"])
                for item in result["project_evidence"]["command_candidates"]
            }
            self.assertIn(("apps/a/package.json", "pnpm run test"), commands)
            self.assertIn(("apps/b/package.json", "yarn run test"), commands)

    def test_extracts_common_non_python_dependency_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text("sqlalchemy==2.0.0\n")
            (root / "go.mod").write_text("module example\nrequire github.com/gin-gonic/gin v1.10.0\n")
            (root / "Cargo.toml").write_text(
                '[package]\nname="demo"\nversion="0.1.0"\n[dependencies]\nqdrant-client="1"\n'
            )
            result = scan_project(root)
            names = {item["name"] for item in result["project_evidence"]["dependency_declarations"]}
            self.assertTrue({"sqlalchemy", "github.com/gin-gonic/gin", "qdrant-client"}.issubset(names))
            self.assertIn("database", result["project_evidence"]["specialized_discovery"])
            self.assertIn("ai", result["project_evidence"]["specialized_discovery"])
    def test_depth_limit_reports_omitted_file_without_reading_its_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (nested / "package.json").write_text(
                '{"dependencies":{"vue":"DEPTH_SENTINEL"}}',
                encoding="utf-8",
            )

            result = scan_project(root, max_depth=1)

            self.assertTrue(result["limits"].get("depth_truncated", False))
            self.assertFalse(result.get("complete", True))
            self.assertIn("nested/package.json", json.dumps(result.get("unverified", [])))
            self.assertNotIn("vue", result["stack_signals"]["frontend"])
            self.assertNotIn("DEPTH_SENTINEL", json.dumps(result))

    def test_zero_depth_reports_bounded_unverified_root_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(4):
                (root / ("long-entry-{:02}.txt".format(index))).write_text(
                    "unread body",
                    encoding="utf-8",
                )

            result = scan_project(
                root,
                max_depth=0,
                max_entries=3,
                max_content_bytes=40,
            )

            self.assertTrue(result["limits"].get("depth_truncated", False))
            self.assertLessEqual(result["limits"].get("unverified_path_bytes", 41), 40)
            self.assertLessEqual(len(result.get("unverified", [])), 3)
            self.assertTrue(result["limits"].get("unverified_paths_truncated", False))

    def test_zero_path_budget_still_reports_an_unverified_reason_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "omitted.txt").write_text("unread body", encoding="utf-8")

            result = scan_project(root, max_depth=0, max_content_bytes=0)

            self.assertEqual([], result.get("unverified", []))
            self.assertGreaterEqual(
                result.get("unverified_summary", {}).get("max-depth", 0),
                1,
            )

    def test_scan_stops_at_directory_entry_budget_and_reports_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                (root / "file-{}.txt".format(index)).write_text("x", encoding="utf-8")

            result = scan_project(root, max_entries=3)

            self.assertEqual(3, result["limits"]["directory_entries_seen"])
            self.assertTrue(result["limits"]["directory_entries_truncated"])

    def test_scan_stops_at_file_count_budget_and_reports_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                (root / "file-{}.txt".format(index)).write_text("x", encoding="utf-8")

            result = scan_project(root, max_files=2)

            self.assertEqual(2, len(result["files"]))
            self.assertTrue(result["limits"]["files_truncated"])

    def test_scan_marks_a_bounded_partial_body_as_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"dependencies":{"vue":"1.0.0"},"padding":"xxxxxxxx"}',
                encoding="utf-8",
            )

            result = scan_project(root, max_file_bytes=16, max_content_bytes=16)
            record = next(item for item in result["files"] if item["path"] == "package.json")

            self.assertTrue(record["content_scanned"])
            self.assertEqual("truncated", record["content_status"])
            self.assertTrue(record["content_truncated"])
            self.assertEqual(16, result["limits"]["content_bytes_read"])
            self.assertEqual([], result["stack_signals"]["frontend"])

    def test_scan_marks_failed_utf8_body_read_unverified_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_bytes(b"\xff\xfe\x00")

            result = scan_project(root)
            record = next(item for item in result["files"] if item["path"] == "package.json")

            self.assertFalse(record["content_scanned"])
            self.assertEqual("unverified", record["content_status"])
            self.assertEqual("invalid-utf8", record["content_reason"])

    def test_scan_records_python_as_toolchain_without_inventing_backend(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                "[project]\nname = 'tool-only'\n",
                encoding="utf-8",
            )

            result = scan_project(root)

            self.assertEqual([], result["stack_signals"]["backend"])
            self.assertEqual(["python"], result["stack_signals"]["toolchains"])

    def test_subprocess_timeout_preempts_a_silent_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            started = time.monotonic()

            with self.assertRaises(subprocess.TimeoutExpired):
                _git_command(
                    root,
                    [sys.executable, "-c", "import time; time.sleep(2)"],
                    timeout_seconds=0.05,
                )

            self.assertLess(time.monotonic() - started, 1.0)

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

    def test_rule_discovery_candidates_cover_modules_roles_and_languages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_fixture("code-chain-multilang", root)

            result = scan_project(root, max_depth=8)
            candidates = result["rule_discovery"]["candidates"]

            self.assertTrue({"vue", "typescript", "java", "go"}.issubset(
                {item["language"] for item in candidates}
            ))
            self.assertTrue(
                {"entry", "interface", "business", "data", "test"}.issubset(
                    {
                        role
                        for item in candidates
                        for role in item["role_hints"]
                    }
                )
            )
            self.assertTrue({"frontend", "java", "go"}.issubset(
                {item["module"] for item in candidates}
            ))
            self.assertEqual(
                [],
                result["rule_discovery"]["uncovered_modules"],
            )

    def test_rule_discovery_never_selects_sensitive_or_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_fixture("code-chain-multilang", root)
            (root / ".env.local").write_text(
                "SECRET_SENTINEL=never-read",
                encoding="utf-8",
            )
            (root / "source_win_env.py").write_text(
                'PASSWORD = "SOURCE_ENV_SENTINEL"\n',
                encoding="utf-8",
            )
            (root / "go" / "internal" / "service" / "secret.key").write_bytes(
                b"\x00\xffSECRET_SENTINEL"
            )

            result = scan_project(root, max_depth=8)
            candidate_paths = {
                item["path"]
                for item in result["rule_discovery"]["candidates"]
            }

            self.assertNotIn(".env.local", candidate_paths)
            self.assertNotIn("source_win_env.py", candidate_paths)
            self.assertNotIn(
                "go/internal/service/secret.key",
                candidate_paths,
            )
            self.assertNotIn("never-read", json.dumps(result))
            self.assertNotIn("SECRET_SENTINEL", json.dumps(result))
            self.assertNotIn("SOURCE_ENV_SENTINEL", json.dumps(result))

    def test_rule_discovery_distributes_candidates_across_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_fixture("code-chain-multilang", root)

            result = scan_project(
                root,
                max_depth=8,
                max_content_bytes=1024,
            )
            candidates = result["rule_discovery"]["candidates"]
            by_module = {
                module: [item for item in candidates if item["module"] == module]
                for module in ("frontend", "java", "go")
            }

            self.assertTrue(all(by_module.values()))
            self.assertTrue(
                all(
                    any(item["content_scanned"] for item in items)
                    for items in by_module.values()
                )
            )

    def test_rule_discovery_prefers_effective_chain_files_over_package_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                "backend/app/runtime_services.py",
                "backend/app/orders/res_orders.py",
                "backend/yw_orders/__init__.py",
                "backend/yw_orders/service.py",
                "backend/yw_orders/repository_ops.py",
                "backend/tests/__init__.py",
                "backend/tests/test_orders_service.py",
                "frontend/tests/order-flow.test.mjs",
            )
            for relative in paths:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# representative\n", encoding="utf-8")

            result = scan_project(root, max_depth=8)
            selected = {
                item["path"] for item in result["rule_discovery"]["candidates"]
            }

            self.assertIn("backend/yw_orders/service.py", selected)
            self.assertIn("backend/yw_orders/repository_ops.py", selected)
            self.assertIn("backend/tests/test_orders_service.py", selected)
            self.assertIn("frontend/tests/order-flow.test.mjs", selected)
            self.assertNotIn("backend/yw_orders/__init__.py", selected)
            self.assertNotIn("backend/tests/__init__.py", selected)

    def test_scan_ignores_local_worktree_and_tool_cache_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                ".worktrees/branch/service.py",
                ".idea/helper.py",
                ".pytest_cache/test_cache.py",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("SENTINEL = 'ignored'\n", encoding="utf-8")

            result = scan_project(root, max_depth=8)

            self.assertNotIn("SENTINEL", json.dumps(result))
            self.assertEqual([], result["rule_discovery"]["candidates"])

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
            self.assertEqual(
                {"frontend": [], "backend": [], "toolchains": []},
                result["stack_signals"],
            )
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

    def test_scan_does_not_mark_small_repository_truncated_when_request_exceeds_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.name", "Scanner Test")
            self._git(root, "config", "user.email", "scanner@example.invalid")
            self._git(root, "commit", "--allow-empty", "-m", "only commit")

            result = scan_project(root, recent_commits=101)

            self.assertEqual(["only commit"], [commit["subject"] for commit in result["git"]["commits"]])
            self.assertFalse(result["git"]["commits_truncated"])

    @staticmethod
    def _git(root: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=str(root),
            check=True,
            capture_output=True,
            text=True,
        )
