"""Static CI telemetry policy tests."""

from pathlib import Path
import tempfile
import unittest

from tools.check_ci_telemetry import check_actions, check_workflows


class CITelemetryPolicyTests(unittest.TestCase):
    def test_repository_workflows_keep_service_telemetry_disabled(self):
        root = Path(__file__).resolve().parents[2] / ".github" / "workflows"
        self.assertEqual(check_workflows(root), [])

    def test_repository_composite_actions_keep_service_telemetry_disabled(self):
        root = Path(__file__).resolve().parents[2] / ".github" / "actions"
        self.assertEqual(check_actions(root), [])

    def test_non_service_workflow_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs.yml").write_text(
                "jobs:\n  docs:\n    run: echo docs\n", encoding="utf-8"
            )
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

    def test_step_env_is_effective(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.yml").write_text(
                "env:\n  SPACE__DISABLE_TELEMETRY: 'true'\n"
                "jobs:\n  service:\n    steps:\n"
                "      - run: regression_ci\n"
                "        env:\n"
                "          SPACE__DISABLE_TELEMETRY: 'true'\n",
                encoding="utf-8",
            )
            self.assertEqual(check_workflows(root), [])

    def test_step_env_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.yml").write_text(
                "env:\n  SPACE__DISABLE_TELEMETRY: 'true'\n"
                "jobs:\n  service:\n"
                "    env:\n"
                "      SPACE__DISABLE_TELEMETRY: 'true'\n"
                "    steps:\n"
                "      - run: regression_ci\n"
                "        env:\n"
                "          SPACE__DISABLE_TELEMETRY: 'false'\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("job service step 0", errors[0])
            self.assertIn("explicitly enabled", errors[0])

    def test_job_env_overrides_workflow_env(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "good.yml").write_text(
                "env:\n  SPACE__DISABLE_TELEMETRY: 'false'\n"
                "jobs:\n  service:\n"
                "    env:\n"
                "      SPACE__DISABLE_TELEMETRY: 'true'\n"
                "    run: regression_ci\n",
                encoding="utf-8",
            )
            self.assertEqual(check_workflows(root), [])

    def test_known_service_job_without_marker_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run-tests.yml").write_text(
                "jobs:\n  e2e:\n    run: echo core\n", encoding="utf-8"
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("job e2e", errors[0])
            self.assertIn("missing SPACE__DISABLE_TELEMETRY=true", errors[0])

    def test_reusable_workflow_callee_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core-smoke.yml").write_text(
                "jobs:\n  p0:\n    uses: ./.github/workflows/p0-acceptance.yml\n",
                encoding="utf-8",
            )
            (root / "p0-acceptance.yml").write_text(
                "jobs:\n  permissions:\n    run: uv run pytest tests/integration/api\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("p0-acceptance.yml job permissions", errors[0])

    def test_missing_reusable_workflow_callee_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core-smoke.yml").write_text(
                "jobs:\n  p0:\n    uses: ./.github/workflows/missing.yml\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("local workflow missing.yml not found", errors[0])

    def test_composite_action_without_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad").mkdir()
            (root / "bad" / "action.yml").write_text(
                "runs:\n  using: composite\n  steps:\n"
                "    - shell: bash\n      run: regression_ci\n",
                encoding="utf-8",
            )
            errors = check_actions(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("step 0", errors[0])
            self.assertIn("missing SPACE__DISABLE_TELEMETRY=true", errors[0])

    def test_only_true_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.yml").write_text(
                "jobs:\n  service:\n    run: regression_ci\n    env:\n      SPACE__DISABLE_TELEMETRY: '1'\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("missing SPACE__DISABLE_TELEMETRY=true", errors[0])

    def test_explicitly_enabled_telemetry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.yml").write_text(
                "jobs:\n  bad:\n    run: regression_ci\n    env:\n      SPACE__DISABLE_TELEMETRY: 'false'\n",
                encoding="utf-8",
            )
            errors = check_workflows(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("explicitly enabled", errors[0])


if __name__ == "__main__":
    unittest.main()
