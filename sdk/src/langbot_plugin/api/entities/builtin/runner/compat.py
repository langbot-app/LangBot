"""Compatibility helpers for Runner DTOs."""

from __future__ import annotations

import pydantic


HOST_RESPONSE_MODEL_CONFIG = pydantic.ConfigDict(extra="ignore")
"""Model config for Host-returned DTOs.

Host API responses may gain optional fields over time. Older SDK versions
should ignore those fields instead of failing validation.
"""
