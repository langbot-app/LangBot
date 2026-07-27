"""Policy helpers for classifying AgentRunner ledger error signals."""

from __future__ import annotations

import json
import re


_INVALID_TOOL_ARGUMENT_PATTERN = re.compile(
    r"invalid json arguments|\b\d+\s+validation errors?\s+for\s+[A-Za-z_][A-Za-z0-9_]*Args\b",
    re.IGNORECASE,
)


def load_ledger_json(value: str | None, *, field: str, failures: list[dict]) -> object:
    """Decode persisted ledger JSON and retain corruption as an invariant failure."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        failures.append({"kind": "invalid_json", "field": field, "reason": str(exc)})
        return {}


def invalid_tool_argument_error_signal(value: str) -> str:
    """Return the persisted signal for malformed model-supplied tool arguments."""
    match = _INVALID_TOOL_ARGUMENT_PATTERN.search(value)
    return match.group(0) if match else ""


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


def classify_tool_authorization(
    calls: list[dict],
    *,
    authorization_mode: str,
) -> tuple[list[dict], list[dict]]:
    """Classify tool names absent from the Host authorization snapshot."""
    if not calls:
        return [], []
    if authorization_mode == "runner-native":
        return [], [
            {
                "kind": "runner_native_tool_calls",
                "calls": calls,
                "reason": (
                    "External runner tool telemetry is not a LangBot Host tool call; "
                    "the runner's own permission system governs it."
                ),
            }
        ]
    return [{"kind": "unauthorized_tool_calls", "calls": calls}], []
