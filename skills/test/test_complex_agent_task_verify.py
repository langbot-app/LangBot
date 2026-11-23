from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


VERIFY_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "langbot-testing"
    / "fixtures"
    / "complex-agent-task"
    / "verify.py"
)
SPEC = importlib.util.spec_from_file_location("complex_agent_task_verify", VERIFY_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComplexAgentTaskVerifyTests(unittest.TestCase):
    def test_accepts_initial_failure_heading(self) -> None:
        self.assertTrue(MODULE.has_initial_failure_section("## Initial failing tests\n- test_price"))

    def test_accepts_baseline_failure_heading(self) -> None:
        self.assertTrue(MODULE.has_initial_failure_section("## Baseline failing tests\n- test_price"))

    def test_accepts_baseline_run_heading_with_failures_in_body(self) -> None:
        report = """\
## Baseline test run (before any edits)

The suite reported FAILED (failures=2). Failing tests:

- test_price
- test_inventory
"""
        self.assertTrue(MODULE.has_initial_failure_section(report))

    def test_rejects_report_without_failure_section(self) -> None:
        self.assertFalse(MODULE.has_initial_failure_section("## Verification\nAll tests pass."))

    def test_rejects_passing_baseline_without_failure_evidence(self) -> None:
        self.assertFalse(MODULE.has_initial_failure_section("## Baseline test run\nAll tests pass."))


if __name__ == "__main__":
    unittest.main()
