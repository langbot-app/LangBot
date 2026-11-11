"""Decide once per Query whether its replies are delivered as a stream."""

from __future__ import annotations

import typing

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

STREAM_OUTPUT_KEY = '_stream_output'


async def adapter_stream_output(adapter: typing.Any) -> bool:
    """Ask an adapter whether the message being handled now should stream."""

    try:
        return bool(await adapter.is_stream_output_supported())
    except AttributeError:
        return False


async def stream_output_enabled(query: pipeline_query.Query) -> bool:
    """Return the streaming mode fixed for this Query's whole turn.

    Ingress records the mode while the adapter can still answer for the inbound
    message. Asking the adapter again later could observe another conversation's
    choice and split one reply into several messages.
    """

    variables = query.variables if isinstance(getattr(query, 'variables', None), dict) else {}
    decided = variables.get(STREAM_OUTPUT_KEY)
    if not isinstance(decided, bool):
        decided = await adapter_stream_output(query.adapter)
        variables[STREAM_OUTPUT_KEY] = decided
    return decided
