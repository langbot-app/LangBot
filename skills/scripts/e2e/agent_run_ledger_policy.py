"""Policy helpers for classifying AgentRunner ledger error signals."""

from __future__ import annotations

import json


def load_ledger_json(value: str | None, *, field: str, failures: list[dict]) -> object:
    """Decode persisted ledger JSON and retain corruption as an invariant failure."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        failures.append({"kind": "invalid_json", "field": field, "reason": str(exc)})
        return {}


def classify_invalid_tool_argument_errors(
    events: list[dict],
    *,
    successful_tool_completion_sequences: list[int],
    run_completed: bool,
) -> tuple[list[dict], list[dict]]:
    """Split malformed tool arguments into recovered warnings and hard failures."""
    failures: list[dict] = []
    warnings: list[dict] = []
    for event in events:
        recovered = run_completed and any(
            sequence > event["sequence"]
            for sequence in successful_tool_completion_sequences
        )
        if recovered:
            warnings.append(
                {
                    "kind": "recovered_tool_argument_error",
                    "event": event,
                    "reason": "The model continued with a later successful tool call and the run completed.",
                }
            )
        else:
            failures.append(event)
    return failures, warnings
