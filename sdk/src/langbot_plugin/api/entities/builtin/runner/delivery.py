"""DeliveryContext as defined in Protocol v1.

Delivery context describes the output surface and platform capabilities.
"""

from __future__ import annotations

import typing
import pydantic

from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionDeliveryCapabilities,
)


class DeliveryContext(pydantic.BaseModel):
    """Delivery context for the agent run.

    Tells the runner what output capabilities are available,
    such as streaming, editing, reactions, and platform-specific features.
    """

    automatic_reply: bool = False
    """Whether returned messages/files are delivered by the Pipeline output stages."""

    surface: str
    """Output surface type (platform, webui, api, etc.)."""

    reply_target: dict[str, typing.Any] | None = None
    """Target for reply (message_id, conversation_id, etc.)."""

    supports_streaming: bool = False
    """Whether streaming output is supported."""

    supports_edit: bool = False
    """Whether message editing is supported."""

    supports_reaction: bool = False
    """Whether message reactions are supported."""

    max_message_size: int | None = None
    """Maximum message size in characters/bytes."""

    interactions: InteractionDeliveryCapabilities | None = None
    """Structured interaction features supported by this delivery surface."""

    platform_capabilities: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """Platform-specific capabilities."""
