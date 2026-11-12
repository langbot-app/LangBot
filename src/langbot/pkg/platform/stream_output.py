"""Streaming support of one reply, for adapters that decide it per inbound message."""

import typing

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events


async def stream_output_supported(
    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
    message_source: platform_events.MessageEvent | None,
) -> bool:
    """Whether the reply to ``message_source`` is streamed.

    One adapter serves many conversations at once, so a preference chosen by the
    client must be read from the message being answered, never from the adapter.
    """
    if callable(getattr(type(adapter), 'is_stream_output_supported_for', None)):
        return await typing.cast(typing.Any, adapter).is_stream_output_supported_for(message_source)
    return await adapter.is_stream_output_supported()
