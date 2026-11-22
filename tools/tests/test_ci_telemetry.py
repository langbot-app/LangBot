"""Static CI telemetry policy tests."""

from pathlib import Path
import tempfile
import unittest

from tools.check_ci_telemetry import check_workflows


class CITelemetryPolicyTests(unittest.TestCase):
    def test_repository_workflows_keep_service_telemetry_disabled(self):
        root = Path(__file__).resolve().parents[2] / ".github" / "workflows"
        self.assertEqual(check_workflows(root), [])

    def test_non_service_workflow_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs.yml").write_text("jobs:\n  docs:\n    run: echo docs\n", encoding="utf-8")
            self.assertEqual(check_workflows(root), [])

    def test_service_job_without_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.yml").write_text(
                "jobs:\n  good:\n    env:\n      SPACE__DISABLE_TELEMETRY: 'true'\n"
                "    run: regression_ci\n  bad:\n    run: regression_ci\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("job bad", errors[0])
            self.assertIn("missing SPACE__DISABLE_TELEMETRY=true", errors[0])

    def test_explicitly_enabled_telemetry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.yml").write_text(
                "jobs:\n  bad:\n    run: regression_ci\n    env:\n"
                "      SPACE__DISABLE_TELEMETRY: 'false'\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("explicitly enabled", errors[0])


if __name__ == "__main__":
    unittest.main()
