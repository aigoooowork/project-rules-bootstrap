import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict
from unittest.mock import patch

from scripts.render_adapters import render_selected_adapters
from scripts.validate_outputs import load_adapter_registry, validate_output_tree


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def tree_snapshot(root: Path) -> Dict[str, str]:
    snapshot = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def add_expected_hash(write: object, content: bytes) -> object:
    object.__setattr__(write, "expected_sha256", sha256_bytes(content))
    return write


def valid_manifest(adapters: list) -> Dict[str, object]:
    rule_id = "backend.repository-boundary"
    confirmation_id = "confirmation.backend.repository-boundary"
    return {
        "version": "1.0",
        "project": {"name": "integration", "language": "en"},
        "scan_baseline": {
            "kind": "full-scan",
            "captured_at": "2026-07-28T00:00:00Z",
            "paths": ["."],
            "fallback_reason": "integration fixture",
        },
        "rules": [
            {
                "id": rule_id,
                "domain": "backend",
                "type": "constraint",
                "status": "confirmed",
                "scope": "src/api/**",
                "text": "API handlers must not access the database directly.",
                "confidence": "high",
                "evidence": [
                    {
                        "kind": "user-confirmation",
                        "location": confirmation_id,
                        "observation": "The user explicitly confirmed the displayed constraint.",
                        "captured_at": "2026-07-28T00:01:00Z",
                    }
                ],
                "confirmation_id": confirmation_id,
                "reason": "Keep persistence behind the repository boundary.",
                "exception_policy": "No exceptions.",
                "verification": "Inspect changed handlers for direct database access.",
            }
        ],
        "adapters": adapters,
        "confirmations": [
            {
                "id": confirmation_id,
                "recorded_at": "2026-07-28T00:01:00Z",
                "decision": "confirmed",
                "scope": "src/api/**",
                "rule_ids": [rule_id],
            }
        ],
    }


VALID_BACKEND_RULE = (
    "# Integration backend\n\n"
    "## Scope\nsrc/api/**\n\n"
    "## Confirmed facts\n- The repository boundary was confirmed.\n\n"
    "## Confirmed constraints\n"
    "<!-- rule-id: backend.repository-boundary -->\n"
    "- API handlers must not access the database directly.\n\n"
    "## Execution rules\n- Keep database access behind repositories.\n\n"
    "## Verification\n- Inspect changed handlers for direct database access.\n\n"
    "## Related rules\n- None.\n"
)


def write_valid_prior_tree(root: Path, adapters: list = None) -> tuple:
    manifest_content = (
        json.dumps(valid_manifest(adapters or []), ensure_ascii=False, indent=2)
        + "\n"
    )
    (root / ".ai" / "rules").mkdir(parents=True)
    (root / ".ai" / "rules" / "backend.md").write_text(
        VALID_BACKEND_RULE,
        encoding="utf-8",
        newline="",
    )
    (root / ".ai" / "rules-manifest.json").write_text(
        manifest_content,
        encoding="utf-8",
        newline="",
    )
    return VALID_BACKEND_RULE, manifest_content


def create_directory_link(link: Path, target: Path) -> None:
    if os.name != "nt":
        link.symlink_to(target, target_is_directory=True)
        return
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError("failed to create test junction: {}".format(result.stderr))


def remove_directory_link(link: Path) -> None:
    if link.is_symlink():
        link.unlink()
    else:
        link.rmdir()


def authorized_initial_managed_plan(
    target_path: str,
    managed_content: str,
    existing: bytes,
) -> tuple:
    from scripts.write_outputs import PlannedWrite

    registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
    registry = load_adapter_registry(registry_path)
    _, manifest_adapters, unverified = render_selected_adapters(
        REPOSITORY_ROOT,
        registry,
        ["codex"],
    )
    if unverified:
        raise AssertionError("bundled codex adapter unexpectedly became unverified")
    manifest_content = (
        json.dumps(valid_manifest(manifest_adapters), ensure_ascii=False, indent=2)
        + "\n"
    )
    return (
        [
            PlannedWrite(".ai/rules/backend.md", VALID_BACKEND_RULE, "create"),
            PlannedWrite(".ai/rules-manifest.json", manifest_content, "create"),
            PlannedWrite(
                target_path,
                managed_content,
                "managed-block",
                sha256_bytes(existing),
            ),
        ],
        registry_path,
    )


class OutputWorkflowTests(unittest.TestCase):
    def test_existing_complete_output_tree_can_be_safely_updated_across_both_gates(self) -> None:
        from scripts.write_outputs import (
            MANAGED_END,
            MANAGED_START,
            PlannedWrite,
            apply_analysis,
            apply_final_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            rendered, manifest_adapters, unverified = render_selected_adapters(
                REPOSITORY_ROOT,
                registry,
                ["codex"],
            )
            self.assertEqual([], unverified)
            old_rule = (
                "# Integration backend\n\n"
                "## Scope\nsrc/api/**\n\n"
                "## Confirmed facts\n- The repository boundary was confirmed.\n\n"
                "## Confirmed constraints\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n\n"
                "## Execution rules\n- Keep database access behind repositories.\n\n"
                "## Verification\n- Inspect changed handlers for direct database access.\n\n"
                "## Related rules\n- None.\n"
            )
            old_analysis = b"# Prior approved analysis\r\n"
            old_manifest_data = valid_manifest(manifest_adapters)
            old_manifest_data["analysis_ownership"] = {
                "version": "1.0",
                "owner": "project-rules-bootstrap",
                "path": ".ai/rules.analysis.md",
                "sha256": sha256_bytes(old_analysis),
            }
            old_manifest = (
                json.dumps(old_manifest_data, ensure_ascii=False, indent=2)
                + "\n"
            )
            old_agents = (
                b"\xef\xbb\xbfowner prefix\r\n"
                + MANAGED_START.encode("utf-8")
                + b"\r\n"
                + rendered[0].content.replace("\n", "\r\n").encode("utf-8")
                + b"\r\n"
                + MANAGED_END.encode("utf-8")
                + b"\r\nowner suffix\r\n"
            )
            (root / ".ai" / "rules").mkdir(parents=True)
            (root / ".ai" / "rules.analysis.md").write_bytes(old_analysis)
            (root / ".ai" / "rules" / "backend.md").write_text(
                old_rule,
                encoding="utf-8",
                newline="",
            )
            (root / ".ai" / "rules-manifest.json").write_text(
                old_manifest,
                encoding="utf-8",
                newline="",
            )
            (root / "AGENTS.md").write_bytes(old_agents)
            (root / "KEEP.bin").write_bytes(b"\x00unchanged\r\n")
            initial = tree_snapshot(root)

            try:
                analysis_changes = apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "# Updated approved analysis\n",
                    approved=True,
                    expected_sha256=sha256_bytes(old_analysis),
                    prior_manifest_sha256=sha256_bytes(old_manifest.encode("utf-8")),
                    registry=registry_path,
                )
            except (FileExistsError, TypeError) as error:
                self.fail("Gate 1 safe update is unavailable: {}".format(error))
            self.assertEqual([".ai/rules.analysis.md"], analysis_changes)
            after_gate_one = tree_snapshot(root)
            self.assertEqual(
                {".ai/rules.analysis.md"},
                {path for path in after_gate_one if after_gate_one[path] != initial[path]},
            )

            new_rule = old_rule.replace("# Integration backend", "# Updated backend")
            updated_analysis = b"# Updated approved analysis\n"
            new_manifest_data = json.loads(old_manifest)
            new_manifest_data["project"]["name"] = "updated integration"
            new_manifest_data["analysis_ownership"]["sha256"] = sha256_bytes(
                updated_analysis
            )
            new_manifest = (
                json.dumps(new_manifest_data, ensure_ascii=False, indent=2)
                + "\n"
            )
            new_testing = (
                "# Testing\n\n"
                "## Scope\ntests/**\n\n"
                "## Confirmed facts\n- None.\n\n"
                "## Confirmed constraints\n\n"
                "## Execution rules\n- Run the documented test command.\n\n"
                "## Verification\n- Inspect the test result.\n\n"
                "## Related rules\n- None.\n"
            )
            writes = [
                add_expected_hash(
                    PlannedWrite(".ai/rules/backend.md", new_rule, "replace-owned"),
                    old_rule.encode("utf-8"),
                ),
                add_expected_hash(
                    PlannedWrite(
                        ".ai/rules-manifest.json",
                        new_manifest,
                        "replace-owned",
                    ),
                    old_manifest.encode("utf-8"),
                ),
                PlannedWrite(".ai/rules/testing.md", new_testing, "create"),
                add_expected_hash(
                    PlannedWrite("AGENTS.md", rendered[0].content + "\nupdated", "managed-block"),
                    old_agents,
                ),
            ]
            try:
                changed = apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                    prior_manifest_sha256=sha256_bytes(old_manifest.encode("utf-8")),
                    registry=registry_path,
                )
            except (FileExistsError, TypeError, ValueError) as error:
                self.fail("Gate 2 safe update is unavailable: {}".format(error))

            self.assertEqual(sorted(write.path for write in writes), changed)
            self.assertEqual(b"\x00unchanged\r\n", (root / "KEEP.bin").read_bytes())
            updated_agents = (root / "AGENTS.md").read_bytes()
            self.assertTrue(updated_agents.startswith(b"\xef\xbb\xbfowner prefix\r\n"))
            self.assertTrue(updated_agents.endswith(b"\r\nowner suffix\r\n"))
            self.assertNotEqual(initial[".ai/rules/backend.md"], tree_snapshot(root)[".ai/rules/backend.md"])
            self.assertEqual([], validate_output_tree(root, registry_path))

    def test_managed_block_update_preserves_every_byte_outside_the_markers(self) -> None:
        from scripts.write_outputs import MANAGED_END, MANAGED_START, PlannedWrite, apply_final_outputs

        cases = {
            "lf": (b"", b"\n"),
            "crlf": (b"", b"\r\n"),
            "bom-lf": (b"\xef\xbb\xbf", b"\n"),
            "bom-crlf": (b"\xef\xbb\xbf", b"\r\n"),
        }
        for name, (bom, newline) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                prefix = bom + b"owner prefix" + newline + MANAGED_START.encode("utf-8")
                suffix = MANAGED_END.encode("utf-8") + newline + b"owner suffix" + newline
                existing = prefix + newline + b"old managed body" + newline + suffix
                target = root / "AGENTS.md"
                target.write_bytes(existing)
                writes, registry_path = authorized_initial_managed_plan(
                    "AGENTS.md",
                    "new managed body",
                    existing,
                )

                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                    registry=registry_path,
                )

                updated = target.read_bytes()
                self.assertTrue(updated.startswith(prefix))
                self.assertTrue(updated.endswith(suffix))

    def test_gate_one_update_requires_exact_path_current_hash_and_regular_file(self) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".ai" / "rules.analysis.md"
            target.parent.mkdir()
            target.write_bytes(b"prior analysis\n")
            before = tree_snapshot(root)

            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    "rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(target.read_bytes()),
                )
            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256="0" * 64,
                )
            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_gate_one_existing_analysis_rejects_self_authorized_hash_without_provenance(
        self,
    ) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".ai" / "rules.analysis.md"
            target.parent.mkdir()
            target.write_bytes(b"unproven analysis\n")
            before = tree_snapshot(root)

            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(target.read_bytes()),
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_gate_one_rejects_old_manifest_without_analysis_ownership_provenance(
        self,
    ) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest_content = write_valid_prior_tree(root)
            target = root / ".ai" / "rules.analysis.md"
            target.write_bytes(b"legacy unproven analysis\n")
            before = tree_snapshot(root)

            with self.assertRaisesRegex(
                ValueError,
                "migrat|re-confirm",
            ):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(target.read_bytes()),
                    prior_manifest_sha256=sha256_bytes(
                        manifest_content.encode("utf-8")
                    ),
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_gate_one_rejects_analysis_symlink_before_reading_or_writing(self) -> None:
        from scripts.write_outputs import apply_analysis

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / "outside-analysis-target.md"
            outside.write_bytes(b"outside sentinel\n")
            link = root / ".ai" / "rules.analysis.md"
            link.parent.mkdir()
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest("symlink creation is unavailable: {}".format(error))

            with self.assertRaises(ValueError):
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "replacement\n",
                    approved=True,
                    expected_sha256=sha256_bytes(outside.read_bytes()),
                )

            self.assertEqual(b"outside sentinel\n", outside.read_bytes())

    def test_gate_two_rejects_hash_mismatch_and_unowned_replacement_atomically(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rule_content = (
                "# Backend\n\n"
                "## Scope\nsrc/api/**\n\n"
                "## Confirmed facts\n- None.\n\n"
                "## Confirmed constraints\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n\n"
                "## Execution rules\n- Keep database access behind repositories.\n\n"
                "## Verification\n- Inspect changed handlers.\n\n"
                "## Related rules\n- None.\n"
            )
            manifest_content = json.dumps(
                valid_manifest([]),
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            (root / ".ai" / "rules").mkdir(parents=True)
            (root / ".ai" / "rules" / "backend.md").write_text(
                rule_content,
                encoding="utf-8",
                newline="",
            )
            (root / ".ai" / "rules-manifest.json").write_text(
                manifest_content,
                encoding="utf-8",
                newline="",
            )
            (root / "README.md").write_bytes(b"user-owned\n")
            before = tree_snapshot(root)
            prior_hash = sha256_bytes(manifest_content.encode("utf-8"))

            mismatch = PlannedWrite(
                ".ai/rules/backend.md",
                rule_content.replace("# Backend", "# Changed"),
                "replace-owned",
                "0" * 64,
            )
            with self.assertRaises(ValueError):
                apply_final_outputs(
                    root,
                    [mismatch],
                    approved_paths=[mismatch.path],
                    approved=True,
                    prior_manifest_sha256=prior_hash,
                )

            unowned = PlannedWrite(
                "README.md",
                "replacement\n",
                "replace-owned",
                sha256_bytes(b"user-owned\n"),
            )
            with self.assertRaises(ValueError):
                apply_final_outputs(
                    root,
                    [unowned],
                    approved_paths=[unowned.path],
                    approved=True,
                    prior_manifest_sha256=prior_hash,
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_managed_block_rejects_missing_duplicate_nested_or_reversed_markers(self) -> None:
        from scripts.write_outputs import MANAGED_END, MANAGED_START, PlannedWrite, apply_final_outputs

        cases = {
            "missing": b"owner content\n",
            "duplicate": (
                MANAGED_START
                + "\n"
                + MANAGED_START
                + "\nbody\n"
                + MANAGED_END
                + "\n"
            ).encode("utf-8"),
            "nested": (
                MANAGED_START
                + "\n"
                + MANAGED_START
                + "\nbody\n"
                + MANAGED_END
                + "\n"
                + MANAGED_END
            ).encode("utf-8"),
            "reversed": (MANAGED_END + "\nbody\n" + MANAGED_START).encode("utf-8"),
        }
        for name, existing in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "AGENTS.md"
                target.write_bytes(existing)
                writes, registry_path = authorized_initial_managed_plan(
                    "AGENTS.md",
                    "replacement",
                    existing,
                )

                with self.assertRaises(ValueError):
                    apply_final_outputs(
                        root,
                        writes,
                        approved_paths=[write.path for write in writes],
                        approved=True,
                        registry=registry_path,
                    )

                self.assertEqual(existing, target.read_bytes())

    def test_initial_managed_block_requires_new_manifest_registry_authorization(
        self,
    ) -> None:
        from scripts.write_outputs import MANAGED_END, MANAGED_START, PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            rendered, manifest_adapters, unverified = render_selected_adapters(
                REPOSITORY_ROOT,
                registry,
                ["codex"],
            )
            self.assertEqual([], unverified)
            existing = (
                "owner prefix\n{}\nold body\n{}\nowner suffix\n".format(
                    MANAGED_START,
                    MANAGED_END,
                )
            ).encode("utf-8")
            target = root / "UNREGISTERED.md"
            target.write_bytes(existing)
            manifest_content = (
                json.dumps(valid_manifest(manifest_adapters), ensure_ascii=False, indent=2)
                + "\n"
            )
            writes = [
                PlannedWrite(".ai/rules-manifest.json", manifest_content, "create"),
                PlannedWrite(
                    "UNREGISTERED.md",
                    rendered[0].content,
                    "managed-block",
                    sha256_bytes(existing),
                ),
            ]
            before = tree_snapshot(root)

            with self.assertRaises(ValueError):
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                    registry=registry_path,
                )

            self.assertEqual(before, tree_snapshot(root))

    def test_replace_race_to_external_link_fails_closed_without_touching_canary(
        self,
    ) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_rule, old_manifest = write_valid_prior_tree(root)
            target = root / ".ai" / "rules" / "backend.md"
            canary = root / "outside-canary.md"
            canary.write_bytes(b"outside canary must remain unchanged\n")
            write = writer.PlannedWrite(
                ".ai/rules/backend.md",
                old_rule.replace("# Integration backend", "# Updated backend"),
                "replace-owned",
                sha256_bytes(old_rule.encode("utf-8")),
            )
            original_revalidate = writer._revalidate_prepared

            def replace_after_revalidation(prepared: object) -> None:
                original_revalidate(prepared)
                target.unlink()
                try:
                    target.symlink_to(canary)
                except OSError:
                    os.link(canary, target)

            with patch.object(
                writer,
                "_revalidate_prepared",
                side_effect=replace_after_revalidation,
            ):
                with self.assertRaises(ValueError):
                    writer.apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                        prior_manifest_sha256=sha256_bytes(
                            old_manifest.encode("utf-8")
                        ),
                    )

            self.assertEqual(
                b"outside canary must remain unchanged\n",
                canary.read_bytes(),
            )

    def test_parent_directory_swap_after_identity_check_never_touches_external_canary(
        self,
    ) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            outside = base / "outside-rules"
            root.mkdir()
            outside.mkdir()
            old_rule, old_manifest = write_valid_prior_tree(root)
            target = root / ".ai" / "rules" / "backend.md"
            os.link(target, outside / "backend.md")
            outside_before = tree_snapshot(outside)
            original_parent = base / "original-rules"
            parent = target.parent
            original_assert = writer._assert_parent_identity
            swapped = False

            def swap_after_successful_check(stage: object) -> None:
                nonlocal swapped
                original_assert(stage)
                if not swapped:
                    parent.rename(original_parent)
                    create_directory_link(parent, outside)
                    swapped = True

            write = writer.PlannedWrite(
                ".ai/rules/backend.md",
                old_rule.replace("# Integration backend", "# Updated backend"),
                "replace-owned",
                sha256_bytes(old_rule.encode("utf-8")),
            )
            try:
                with patch.object(
                    writer,
                    "_assert_parent_identity",
                    side_effect=swap_after_successful_check,
                ):
                    with self.assertRaises((OSError, RuntimeError, ValueError)):
                        writer.apply_final_outputs(
                            root,
                            [write],
                            approved_paths=[write.path],
                            approved=True,
                            prior_manifest_sha256=sha256_bytes(
                                old_manifest.encode("utf-8")
                            ),
                        )

                self.assertTrue(swapped)
                self.assertEqual(outside_before, tree_snapshot(outside))
            finally:
                if parent.exists() or parent.is_symlink():
                    remove_directory_link(parent)
                if original_parent.exists():
                    original_parent.rename(parent)

    def test_prior_validation_rejects_linked_canonical_root_without_reading_canary(
        self,
    ) -> None:
        from scripts.write_outputs import apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            outside = base / "outside-canonical"
            (root / ".ai").mkdir(parents=True)
            outside.mkdir()
            manifest_content = (
                json.dumps(valid_manifest([]), ensure_ascii=False, indent=2) + "\n"
            )
            (root / ".ai" / "rules-manifest.json").write_text(
                manifest_content,
                encoding="utf-8",
                newline="",
            )
            canary = outside / "backend.md"
            canary.write_text("CANARY_BODY_MUST_NOT_BE_READ", encoding="utf-8")
            linked_rules = root / ".ai" / "rules"
            create_directory_link(linked_rules, outside)
            original_read_text = Path.read_text
            canary_reads = []

            def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
                if path.resolve(strict=False) == canary.resolve(strict=False):
                    canary_reads.append(path)
                    raise AssertionError("outside canonical canary was read")
                return original_read_text(path, *args, **kwargs)

            try:
                with patch.object(Path, "read_text", guarded_read_text):
                    with self.assertRaises(ValueError):
                        apply_final_outputs(
                            root,
                            [],
                            approved_paths=[],
                            approved=True,
                            prior_manifest_sha256=sha256_bytes(
                                manifest_content.encode("utf-8")
                            ),
                        )
            finally:
                if linked_rules.exists():
                    linked_rules.rmdir()

            self.assertEqual([], canary_reads)

    def test_commit_failure_rolls_back_replacements_and_deletes_creates(self) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_rule, old_manifest = write_valid_prior_tree(root)
            new_manifest = old_manifest.replace(
                '"integration"',
                '"updated integration"',
            )
            new_testing = (
                "# Testing\n\n"
                "## Scope\ntests/**\n\n"
                "## Confirmed facts\n- None.\n\n"
                "## Confirmed constraints\n\n"
                "## Execution rules\n- Run the documented test command.\n\n"
                "## Verification\n- Inspect the test result.\n\n"
                "## Related rules\n- None.\n"
            )
            writes = [
                writer.PlannedWrite(
                    ".ai/rules/backend.md",
                    old_rule.replace("# Integration backend", "# Updated backend"),
                    "replace-owned",
                    sha256_bytes(old_rule.encode("utf-8")),
                ),
                writer.PlannedWrite(".ai/rules/testing.md", new_testing, "create"),
                writer.PlannedWrite(
                    ".ai/rules-manifest.json",
                    new_manifest,
                    "replace-owned",
                    sha256_bytes(old_manifest.encode("utf-8")),
                ),
            ]
            before = tree_snapshot(root)
            real_commit = writer._commit_existing_stage
            commit_calls = 0

            def fail_after_second_existing_commit(stage: object) -> None:
                nonlocal commit_calls
                real_commit(stage)
                commit_calls += 1
                if commit_calls == 2:
                    raise OSError("injected second existing commit failure")

            with patch.object(
                writer,
                "_commit_existing_stage",
                side_effect=fail_after_second_existing_commit,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "injected second existing commit failure",
                ):
                    writer.apply_final_outputs(
                        root,
                        writes,
                        approved_paths=[write.path for write in writes],
                        approved=True,
                        prior_manifest_sha256=sha256_bytes(
                            old_manifest.encode("utf-8")
                        ),
                    )

            self.assertEqual(before, tree_snapshot(root))

    @unittest.skipUnless(os.name == "nt", "delete-sharing lock is Windows-specific")
    def test_rollback_failure_preserves_backup_and_writes_recovery_journal(self) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_rule, old_manifest = write_valid_prior_tree(root)
            target = root / ".ai" / "rules" / "backend.md"
            write = writer.PlannedWrite(
                ".ai/rules/backend.md",
                old_rule.replace("# Integration backend", "# Updated backend"),
                "replace-owned",
                sha256_bytes(old_rule.encode("utf-8")),
            )
            original_commit = writer._commit_existing_stage
            locks = []

            def fail_after_commit(stage: object) -> None:
                original_commit(stage)
                locks.append(target.open("rb"))
                raise OSError("injected failure after install")

            try:
                with patch.object(
                    writer,
                    "_commit_existing_stage",
                    side_effect=fail_after_commit,
                ):
                    with self.assertRaises(RuntimeError) as raised:
                        writer.apply_final_outputs(
                            root,
                            [write],
                            approved_paths=[write.path],
                            approved=True,
                            prior_manifest_sha256=sha256_bytes(
                                old_manifest.encode("utf-8")
                            ),
                        )

                backups = list(
                    target.parent.glob(
                        ".backend.md.project-rules-bootstrap-backup-*.tmp"
                    )
                )
                journals = list(
                    root.glob(".project-rules-bootstrap-recovery-*.json")
                )
                self.assertEqual(1, len(backups))
                self.assertEqual(1, len(journals))
                self.assertIn(backups[0].relative_to(root).as_posix(), str(raised.exception))
                journal = json.loads(journals[0].read_text(encoding="utf-8"))
                self.assertEqual(".ai/rules/backend.md", journal["entries"][0]["path"])
                self.assertEqual(
                    backups[0].relative_to(root).as_posix(),
                    journal["entries"][0]["backup_path"],
                )
                self.assertNotIn("content", json.dumps(journal))
            finally:
                for lock in locks:
                    lock.close()

    def test_staging_failure_removes_every_temporary_file_before_returning(self) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write = writer.PlannedWrite("NEW.md", "new content\n", "create")
            before = tree_snapshot(root)
            real_stage = writer._stage_bytes
            calls = 0

            def fail_second_stage(*args: object, **kwargs: object) -> tuple:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected backup staging failure")
                return real_stage(*args, **kwargs)

            with patch.object(writer, "_stage_bytes", side_effect=fail_second_stage):
                with self.assertRaisesRegex(
                    OSError,
                    "injected backup staging failure",
                ):
                    writer.apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                    )

            self.assertEqual(before, tree_snapshot(root))

    def test_completed_namespace_move_is_detected_and_rolled_back_when_return_raises(
        self,
    ) -> None:
        import scripts.write_outputs as writer
        from scripts.safe_fs import DirectoryHandle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_rule, old_manifest = write_valid_prior_tree(root)
            write = writer.PlannedWrite(
                ".ai/rules/backend.md",
                old_rule.replace("# Integration backend", "# Updated backend"),
                "replace-owned",
                sha256_bytes(old_rule.encode("utf-8")),
            )
            before = tree_snapshot(root)
            original_move = DirectoryHandle.move
            injected = False

            def raise_after_claim(
                handle: object,
                source: str,
                destination: str,
                **kwargs: object,
            ) -> tuple:
                nonlocal injected
                outcome = original_move(
                    handle,
                    source,
                    destination,
                    **kwargs,
                )
                if not injected and source == "backend.md":
                    injected = True
                    raise OSError("injected exception after namespace mutation")
                return outcome

            with patch.object(
                DirectoryHandle,
                "move",
                new=raise_after_claim,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "injected exception after namespace mutation",
                ):
                    writer.apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                        prior_manifest_sha256=sha256_bytes(
                            old_manifest.encode("utf-8")
                        ),
                    )

            self.assertTrue(injected)
            self.assertEqual(before, tree_snapshot(root))
            self.assertEqual(
                [],
                list(root.rglob(".project-rules-bootstrap-recovery-*.json")),
            )

    def test_partial_create_move_is_rolled_back_when_source_unlink_fails(
        self,
    ) -> None:
        import scripts.write_outputs as writer
        from scripts.safe_fs import (
            DirectoryHandle,
            MoveOutcome,
            NamespaceMutationError,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write = writer.PlannedWrite("NEW.md", "new content\n", "create")
            before = tree_snapshot(root)
            original_move = DirectoryHandle.move
            injected = False

            def fail_after_create_link(
                handle: object,
                source: str,
                destination: str,
                **kwargs: object,
            ) -> MoveOutcome:
                nonlocal injected
                if (
                    not injected
                    and destination == write.path
                    and not kwargs["replace"]
                ):
                    injected = True
                    os.link(
                        handle.display_path / source,
                        handle.display_path / destination,
                    )
                    installed = handle.snapshot(destination)
                    raise NamespaceMutationError(
                        "injected source unlink failure after destination link",
                        MoveOutcome(installed.identity, False, True),
                    )
                return original_move(
                    handle,
                    source,
                    destination,
                    **kwargs,
                )

            with patch.object(
                DirectoryHandle,
                "move",
                new=fail_after_create_link,
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "injected source unlink failure",
                ):
                    writer.apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                    )

            self.assertTrue(injected)
            self.assertFalse((root / write.path).exists())
            self.assertEqual(before, tree_snapshot(root))
            self.assertEqual([], list(root.glob(".*.tmp")))

    def test_gate_two_rechecks_pinned_analysis_before_installing_manifest(
        self,
    ) -> None:
        import scripts.write_outputs as writer
        from scripts.safe_fs import DirectoryHandle, FileSnapshot

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = b"# Approved analysis\n"
            writer.apply_analysis(
                root,
                ".ai/rules.analysis.md",
                analysis.decode("utf-8"),
                approved=True,
            )
            manifest = valid_manifest([])
            manifest["analysis_ownership"] = {
                "version": "1.0",
                "owner": "project-rules-bootstrap",
                "path": ".ai/rules.analysis.md",
                "sha256": sha256_bytes(analysis),
            }
            manifest_content = (
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            )
            writes = [
                writer.PlannedWrite(
                    ".ai/rules-manifest.json",
                    manifest_content,
                    "create",
                ),
                writer.PlannedWrite(
                    ".ai/rules/backend.md",
                    VALID_BACKEND_RULE,
                    "create",
                ),
            ]
            original_commit_create = writer._commit_create_stage
            original_snapshot = DirectoryHandle.snapshot
            raced = False

            def replace_analysis_after_rule_commit(stage: object) -> None:
                nonlocal raced
                original_commit_create(stage)
                if stage.prepared.path == ".ai/rules/backend.md" and not raced:
                    raced = True

            def expose_concurrent_analysis(
                handle: object,
                name: str,
            ) -> FileSnapshot:
                if (
                    raced
                    and handle.display_path == root / ".ai"
                    and name == "rules.analysis.md"
                ):
                    return FileSnapshot(
                        b"# Concurrent replacement\n",
                        ("concurrent", "replacement", False),
                    )
                return original_snapshot(handle, name)

            with patch.object(
                writer,
                "_commit_create_stage",
                side_effect=replace_analysis_after_rule_commit,
            ), patch.object(
                DirectoryHandle,
                "snapshot",
                new=expose_concurrent_analysis,
            ):
                with self.assertRaises(ValueError):
                    writer.apply_final_outputs(
                        root,
                        writes,
                        approved_paths=[write.path for write in writes],
                        approved=True,
                    )

            self.assertTrue(raced)
            self.assertEqual(
                analysis,
                (root / ".ai" / "rules.analysis.md").read_bytes(),
            )
            self.assertFalse((root / ".ai" / "rules-manifest.json").exists())
            self.assertFalse((root / ".ai" / "rules" / "backend.md").exists())

    def test_managed_path_authorization_failure_closes_analysis_guard(
        self,
    ) -> None:
        import scripts.write_outputs as writer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis = b"# Approved analysis\n"
            writer.apply_analysis(
                root,
                ".ai/rules.analysis.md",
                analysis.decode("utf-8"),
                approved=True,
            )
            manifest = valid_manifest([])
            manifest["analysis_ownership"] = {
                "version": "1.0",
                "owner": "project-rules-bootstrap",
                "path": ".ai/rules.analysis.md",
                "sha256": sha256_bytes(analysis),
            }
            existing = (
                "owner prefix\n{}\nold body\n{}\nowner suffix\n".format(
                    writer.MANAGED_START,
                    writer.MANAGED_END,
                )
            ).encode("utf-8")
            (root / "UNREGISTERED.md").write_bytes(existing)
            writes = [
                writer.PlannedWrite(
                    ".ai/rules-manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    "create",
                ),
                writer.PlannedWrite(
                    "UNREGISTERED.md",
                    "replacement",
                    "managed-block",
                    sha256_bytes(existing),
                ),
            ]
            before = tree_snapshot(root)
            captured_guards = []
            real_validate = writer._validate_planned_analysis_ownership

            def capture_guard(*args: object, **kwargs: object) -> object:
                guard = real_validate(*args, **kwargs)
                captured_guards.append(guard)
                return guard

            with patch.object(
                writer,
                "_validate_planned_analysis_ownership",
                side_effect=capture_guard,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "not authorized",
                ):
                    writer.apply_final_outputs(
                        root,
                        writes,
                        approved_paths=[write.path for write in writes],
                        approved=True,
                    )

            self.assertEqual(1, len(captured_guards))
            guard = captured_guards[0]
            self.assertIsNotNone(guard)
            with self.assertRaisesRegex(ValueError, "file handle is closed"):
                guard.pinned_file.snapshot()
            with self.assertRaisesRegex(ValueError, "directory chain is closed"):
                _ = guard.chain.parent
            self.assertEqual(before, tree_snapshot(root))

    def test_post_commit_backup_cleanup_failure_is_journaled_and_closes_handles(
        self,
    ) -> None:
        import scripts.write_outputs as writer
        from scripts.safe_fs import DirectoryHandle

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_rule, old_manifest = write_valid_prior_tree(root)
            updated_rule = old_rule.replace(
                "# Integration backend",
                "# Updated backend",
            )
            write = writer.PlannedWrite(
                ".ai/rules/backend.md",
                updated_rule,
                "replace-owned",
                sha256_bytes(old_rule.encode("utf-8")),
            )
            original_remove = DirectoryHandle.remove_file
            original_close = writer._close_prepared_chains
            captured_chains = []
            injected = False

            def fail_backup_cleanup(
                handle: object,
                name: str,
                **kwargs: object,
            ) -> None:
                nonlocal injected
                if (
                    not injected
                    and ".project-rules-bootstrap-backup-" in name
                ):
                    injected = True
                    raise OSError("injected committed-backup cleanup failure")
                original_remove(handle, name, **kwargs)

            def capture_closed_chains(prepared: object) -> None:
                captured_chains.extend(
                    item.parent_chain
                    for item in prepared
                    if item.parent_chain is not None
                )
                original_close(prepared)

            with patch.object(
                DirectoryHandle,
                "remove_file",
                new=fail_backup_cleanup,
            ), patch.object(
                writer,
                "_close_prepared_chains",
                side_effect=capture_closed_chains,
            ):
                try:
                    changed = writer.apply_final_outputs(
                        root,
                        [write],
                        approved_paths=[write.path],
                        approved=True,
                        prior_manifest_sha256=sha256_bytes(
                            old_manifest.encode("utf-8")
                        ),
                    )
                except OSError:
                    changed = None

            self.assertTrue(injected)
            self.assertEqual([write.path], changed)
            self.assertEqual(
                updated_rule,
                (root / ".ai" / "rules" / "backend.md").read_text(
                    encoding="utf-8"
                ),
            )
            journals = list(
                root.glob(".project-rules-bootstrap-cleanup-*.json")
            )
            self.assertEqual(1, len(journals))
            journal = json.loads(journals[0].read_text(encoding="utf-8"))
            self.assertEqual("committed-cleanup-required", journal["status"])
            self.assertNotIn("content", json.dumps(journal))
            self.assertTrue(captured_chains)
            self.assertTrue(all(chain._closed for chain in captured_chains))

    def test_write_plan_rejects_windows_ads_path_before_any_write(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in (
                "README.md:private",
                "nested:stream/README.md",
                "nested/README.md:private",
            ):
                with self.subTest(path=path):
                    rejected_by_portable_validation = False
                    try:
                        apply_final_outputs(
                            root,
                            [PlannedWrite(path, "unsafe\n", "create")],
                            approved_paths=[path],
                            approved=True,
                        )
                    except ValueError:
                        rejected_by_portable_validation = True
                    except OSError:
                        pass
                    self.assertTrue(rejected_by_portable_validation)
                    self.assertEqual({}, tree_snapshot(root))

    def test_two_gates_limit_real_file_changes_and_all_adapters_validate(self) -> None:
        from scripts.write_outputs import (
            MANAGED_END,
            MANAGED_START,
            PlannedWrite,
            apply_analysis,
            apply_final_outputs,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("owner documentation\n", encoding="utf-8")
            (root / "KEEP.md").write_text("never overwrite me\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "owner prefix\n{}\nold managed routing\n{}\nowner suffix\n".format(
                    MANAGED_START, MANAGED_END
                ),
                encoding="utf-8",
            )
            initial = tree_snapshot(root)

            self.assertEqual(
                [],
                apply_analysis(
                    root,
                    ".ai/rules.analysis.md",
                    "# Approved analysis\n",
                    approved=False,
                ),
            )
            self.assertEqual(initial, tree_snapshot(root))

            analysis_changes = apply_analysis(
                root,
                ".ai/rules.analysis.md",
                "# Approved analysis\n",
                approved=True,
            )
            self.assertEqual([".ai/rules.analysis.md"], analysis_changes)
            after_gate_one = tree_snapshot(root)
            self.assertEqual(
                {".ai/rules.analysis.md"},
                set(after_gate_one) - set(initial),
            )

            registry_path = REPOSITORY_ROOT / "references" / "adapters.json"
            registry = load_adapter_registry(registry_path)
            selected = [adapter["id"] for adapter in registry["adapters"]]
            rendered, manifest_adapters, unverified = render_selected_adapters(
                REPOSITORY_ROOT, registry, selected
            )
            self.assertEqual([], unverified)
            rule_content = (
                "# Integration backend\n\n"
                "## Scope\nsrc/api/**\n\n"
                "## Confirmed facts\n- The repository boundary was confirmed.\n\n"
                "## Confirmed constraints\n"
                "<!-- rule-id: backend.repository-boundary -->\n"
                "- API handlers must not access the database directly.\n\n"
                "## Execution rules\n- Keep database access behind repositories.\n\n"
                "## Verification\n- Inspect changed handlers for direct database access.\n\n"
                "## Related rules\n- None.\n"
            )
            manifest_data = valid_manifest(manifest_adapters)
            manifest_data["analysis_ownership"] = {
                "version": "1.0",
                "owner": "project-rules-bootstrap",
                "path": ".ai/rules.analysis.md",
                "sha256": sha256_bytes(b"# Approved analysis\n"),
            }
            manifest_content = (
                json.dumps(
                    manifest_data,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            writes = [
                PlannedWrite(".ai/rules/backend.md", rule_content, "create"),
                PlannedWrite(".ai/rules-manifest.json", manifest_content, "create"),
            ]
            for adapter in rendered:
                mode = "managed-block" if adapter.path == "AGENTS.md" else "create"
                write = PlannedWrite(adapter.path, adapter.content, mode)
                if mode == "managed-block":
                    add_expected_hash(write, (root / adapter.path).read_bytes())
                writes.append(write)
            approved_paths = [write.path for write in writes]

            self.assertEqual(
                [],
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=approved_paths,
                    approved=False,
                ),
            )
            self.assertEqual(after_gate_one, tree_snapshot(root))

            changed = apply_final_outputs(
                root,
                writes,
                approved_paths=approved_paths,
                approved=True,
            )

            self.assertEqual(sorted(approved_paths), changed)
            self.assertEqual("never overwrite me\n", (root / "KEEP.md").read_text(encoding="utf-8"))
            agents = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(agents.startswith("owner prefix\n"))
            self.assertTrue(agents.endswith("owner suffix\n"))
            self.assertNotIn("old managed routing", agents)
            self.assertEqual([], validate_output_tree(root, registry_path))

    def test_final_gate_preflight_never_overwrites_an_unowned_file(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "RULES.md").write_text("owner content\n", encoding="utf-8")
            before = tree_snapshot(root)
            writes = [
                PlannedWrite("RULES.md", "generated content\n", "create"),
                PlannedWrite(".ai/rules/project.md", "# Project\n", "create"),
            ]

            with self.assertRaises(FileExistsError):
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                )

            self.assertEqual(before, tree_snapshot(root))

    @unittest.skipUnless(os.name == "nt", "case aliases are a Windows path concern")
    def test_final_gate_rejects_case_alias_paths_before_any_write(self) -> None:
        from scripts.write_outputs import PlannedWrite, apply_final_outputs

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writes = [
                PlannedWrite("NEW.md", "first\n", "create"),
                PlannedWrite("new.md", "second\n", "create"),
            ]

            try:
                apply_final_outputs(
                    root,
                    writes,
                    approved_paths=[write.path for write in writes],
                    approved=True,
                )
            except (FileExistsError, ValueError):
                pass

            self.assertEqual({}, tree_snapshot(root))


if __name__ == "__main__":
    unittest.main()
