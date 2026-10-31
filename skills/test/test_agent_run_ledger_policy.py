from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "e2e"))

from agent_run_ledger_policy import (  # noqa: E402
    classify_invalid_tool_argument_errors,
    classify_tool_authorization,
    invalid_tool_argument_error_signal,
    load_ledger_json,
)


class AgentRunLedgerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = {
            "sequence": 10,
            "type": "tool.call.completed",
            "signal": "Invalid JSON arguments",
        }

    def test_completed_run_with_later_success_is_warning(self) -> None:
        failures, warnings = classify_invalid_tool_argument_errors(
            [self.event],
            successful_tool_completion_sequences=[12],
            run_completed=True,
        )

        self.assertEqual(failures, [])
        self.assertEqual(warnings[0]["kind"], "recovered_tool_argument_error")

    def test_completed_run_without_later_success_still_fails(self) -> None:
        failures, warnings = classify_invalid_tool_argument_errors(
            [self.event],
            successful_tool_completion_sequences=[8],
            run_completed=True,
        )

        self.assertEqual(failures, [self.event])
        self.assertEqual(warnings, [])

    def test_incomplete_run_still_fails_even_with_later_success(self) -> None:
        failures, warnings = classify_invalid_tool_argument_errors(
            [self.event],
            successful_tool_completion_sequences=[12],
            run_completed=False,
        )

        self.assertEqual(failures, [self.event])
        self.assertEqual(warnings, [])

    def test_malformed_persisted_event_json_remains_an_invariant_failure(self) -> None:
        failures: list[dict] = []

        value = load_ledger_json(
            '{"tool_call_id":',
            field="agent_run_event[10].data_json",
            failures=failures,
        )

        self.assertEqual(value, {})
        self.assertEqual(failures[0]["kind"], "invalid_json")
        self.assertEqual(failures[0]["field"], "agent_run_event[10].data_json")

    def test_detects_pydantic_tool_argument_validation_error(self) -> None:
        signal = invalid_tool_argument_error_signal(
            "1 validation error for RetrieveKnowledgeArgs\n"
            "kb_id\n  Field required [type=missing, input_value={'top_k': 3}, input_type=dict]"
        )

        self.assertEqual(signal, "1 validation error for RetrieveKnowledgeArgs")

    def test_ignores_unrelated_tool_execution_error(self) -> None:
        self.assertEqual(invalid_tool_argument_error_signal("Exit code 1"), "")

    def test_strict_mode_rejects_tool_absent_from_host_authorization(self) -> None:
        call = {"tool_call_id": "call-1", "tool_name": "Read"}

        failures, warnings = classify_tool_authorization([call], authorization_mode="strict")

        self.assertEqual(failures, [{"kind": "unauthorized_tool_calls", "calls": [call]}])
        self.assertEqual(warnings, [])

    def test_runner_native_mode_records_non_host_tool_as_warning(self) -> None:
        call = {"tool_call_id": "call-1", "tool_name": "Read"}

        failures, warnings = classify_tool_authorization([call], authorization_mode="runner-native")

        self.assertEqual(failures, [])
        self.assertEqual(warnings[0]["kind"], "runner_native_tool_calls")
        self.assertEqual(warnings[0]["calls"], [call])


if __name__ == "__main__":
    unittest.main()
