"""Import-safe observability helpers for parser components."""

from .telemetry import (
    ParserTelemetry,
    TelemetryRegistry,
    binding_scope,
    get_telemetry,
    release_telemetry,
)

__all__ = [
    "ParserTelemetry",
    "TelemetryRegistry",
    "binding_scope",
    "get_telemetry",
    "release_telemetry",
]
