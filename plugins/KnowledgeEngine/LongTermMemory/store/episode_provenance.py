"""Explicit fact time and declared evidence, independent of storage timestamps."""

from datetime import datetime, timezone
from typing import Any

PROVENANCE_FIELDS = (
    "event_at",
    "valid_from",
    "valid_until",
    "source_ref",
    "claim_type",
)
CLAIM_TYPES = {"unknown", "user_statement", "inference"}


def normalize_provenance(values: dict[str, Any]) -> dict[str, str]:
    result = {}
    parsed_times = {}
    for field in ("event_at", "valid_from", "valid_until"):
        value = values.get(field, "")
        if not isinstance(value, str):
            raise ValueError(
                f"{field} must be an ISO-8601 string with an explicit timezone"
            )
        if not value.strip():
            result[field] = ""
            continue
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"{field} must be an ISO-8601 timestamp with an explicit timezone"
            ) from exc
        if parsed.tzinfo is None:
            raise ValueError(f"{field} must include an explicit timezone")
        try:
            parsed_times[field] = parsed.astimezone(timezone.utc)
            result[field] = parsed_times[field].isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError) as exc:
            raise ValueError(
                f"{field} is outside the supported UTC date range"
            ) from exc
    if (
        result["valid_from"]
        and result["valid_until"]
        and parsed_times["valid_from"] >= parsed_times["valid_until"]
    ):
        raise ValueError(
            "valid_from must be earlier than valid_until; validity uses [from, until)"
        )
    source_ref = values.get("source_ref", "")
    if not isinstance(source_ref, str) or len(source_ref) > 1024:
        raise ValueError("source_ref must be a string of at most 1024 characters")
    result["source_ref"] = source_ref.strip()
    claim_type = values.get("claim_type", "unknown")
    if not isinstance(claim_type, str) or claim_type not in CLAIM_TYPES:
        raise ValueError("claim_type must be unknown, user_statement, or inference")
    result["claim_type"] = claim_type
    return result


def read_provenance(metadata: dict[str, Any]) -> dict[str, str]:
    """Old records have unknown provenance, never inferred evidence."""
    return {
        field: metadata.get(field, "unknown" if field == "claim_type" else "")
        for field in PROVENANCE_FIELDS
    }
