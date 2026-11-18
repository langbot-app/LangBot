"""Portable, per-call model reasoning levels."""

from typing import Literal

ReasoningLevel = Literal[
    "provider_default",
    "disabled",
    "enabled",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]
