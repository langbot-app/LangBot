from __future__ import annotations

from typing import Any

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import context, events
from langbot_plugin.api.entities.builtin.provider.message import Message


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return "".join(parts)


def _message_text(message: Any) -> str:
    if message is None:
        return ""
    return _content_text(getattr(message, "content", None))


def _message_chain_text(message_chain: Any) -> str:
    if message_chain is None:
        return ""
    try:
        return str(message_chain)
    except Exception:
        return ""


async def _current_user_text(event_context: context.EventContext) -> str:
    try:
        query_var_text = await event_context.get_query_var("user_message_text")
    except Exception:
        query_var_text = None
    if query_var_text:
        return str(query_var_text)

    query = getattr(event_context.event, "query", None)
    if query is not None:
        message_chain_text = _message_chain_text(getattr(query, "message_chain", None))
        if message_chain_text:
            return message_chain_text

        user_message_text = _message_text(getattr(query, "user_message", None))
        if user_message_text:
            return user_message_text

    return "\n".join(
        text for text in (_message_text(message) for message in event_context.event.prompt) if text
    )


class PromptProbeEventListener(EventListener):
    async def initialize(self) -> None:
        await super().initialize()

        @self.handler(events.PromptPreProcessing)
        async def on_prompt_pre_processing(event_context: context.EventContext) -> None:
            if "qa-effective-prompt" not in await _current_user_text(event_context):
                return

            event_context.event.default_prompt.append(
                Message(
                    role="system",
                    content=(
                        "QA prompt probe: if the current user message contains "
                        "qa-effective-prompt, reply only PROMPT_PREPROCESS_OK."
                    ),
                )
            )
