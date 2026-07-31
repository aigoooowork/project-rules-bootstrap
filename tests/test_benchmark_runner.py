import unittest

from benchmarks.run_benchmark import summarize_result


class BenchmarkRunnerTests(unittest.TestCase):
    def test_summary_records_scan_limits_candidates_and_grounding(self) -> None:
        scan = {
            "complete": False,
            "files": [{"path": "src/app.py"}, {"path": "tests/test_app.py"}],
            "modules": [{"path": "src"}],
            "rule_discovery": {"candidates": [{"path": "src/app.py"}]},
            "limits": {
                "content_bytes_read": 123,
                "depth_truncated": True,
                "files_truncated": False,
            },
        }
        qualities = [
            {
                "issues": [],
                "existing_path_anchors": 2,
                "existing_path_anchor_paths": ["src/app.py", "tests/test_app.py"],
                "candidate_symbol_anchors": 3,
                "symbol_anchors": 3,
                "chain_signals": 1,
                "verification_commands": 1,
            }
        ]

        result = summarize_result(scan, 12.345, qualities)

        self.assertEqual(12.345, result["elapsed_ms"])
        self.assertFalse(result["scan_complete"])
        self.assertEqual(2, result["files_seen"])
        self.assertEqual(1, result["candidate_count"])
        self.assertEqual(["depth_truncated"], result["active_limits"])
        self.assertEqual(1, result["grounded_rule_files"])
        self.assertEqual(2, result["existing_path_anchors"])
        self.assertEqual(0.5, result["scanner_anchor_coverage"])


if __name__ == "__main__":
    unittest.main()
