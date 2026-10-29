from __future__ import annotations

import re
import logging
import traceback
from urllib.parse import urlsplit, urlunsplit

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


URL_PATTERN = re.compile(r'https?://[^\s<>\]\)，。！？、]+')

logger = logging.getLogger("URLSummary.detector")

DEFAULT_MAX_CONTENT_LENGTH = 8000
MAX_CONTENT_LENGTH = 100_000


def _clamp_max_content_length(value) -> int:
    """Keep the configured extraction length inside a sane range."""
    try:
        length = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONTENT_LENGTH
    return max(1, min(length, MAX_CONTENT_LENGTH))


def _strip_url_tail(value: str) -> str:
    """Fallback scrub for a URL that :func:`urlsplit` cannot parse."""
    head = re.split(r'([?#])', value, maxsplit=1)[0]
    return re.sub(r'//[^/@]*@', '//', head)


def _redact_url(url: str) -> str:
    """Drop userinfo, the query string and the fragment from a URL."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        try:
            port = parts.port
        except ValueError:
            # A non-numeric port makes ``port`` raise; the host is still known.
            port = None
    except (AttributeError, ValueError):
        return _strip_url_tail(str(url))

    if not host:
        return _strip_url_tail(str(url))

    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, '', ''))


_URL_IN_TEXT = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s'\"<>()\[\],;]+")


def _redact_text(text: str) -> str:
    """Redact credentials/query/fragment from every URL inside ``text``.

    This is the last boundary before an exception or a traceback goes to the
    shared logger, so a URL that slipped into a chained cause cannot be logged
    in its raw form.
    """
    if not text:
        return text
    return _URL_IN_TEXT.sub(lambda match: _redact_url(match.group(0)), str(text))


class URLDetector(EventListener):
    """Detects URLs in messages and triggers auto-summarization."""

    def __init__(self):
        super().__init__()

        @self.handler(events.PersonMessageReceived)
        async def on_person_message(event_context: context.EventContext):
            await self._handle_message(event_context)

        @self.handler(events.GroupMessageReceived)
        async def on_group_message(event_context: context.EventContext):
            await self._handle_message(event_context)

    async def _handle_message(self, event_context: context.EventContext):
        try:
            event = event_context.event

            # Extract plain text from message chain
            text_parts = []
            for component in event.message_chain:
                if isinstance(component, platform_message.Plain):
                    text_parts.append(component.text)

            text = "".join(text_parts).strip()
            if not text:
                return

            # Find URLs
            urls = URL_PATTERN.findall(text)
            if not urls:
                return

            # Prevent default LLM response and subsequent plugins
            event_context.prevent_default()
            event_context.prevent_postorder()

            # Deduplicate, take first 3
            seen = set()
            unique_urls = []
            for url in urls:
                url = url.rstrip('.,;:!?')
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
                if len(unique_urls) >= 3:
                    break

            plugin = self.plugin
            config = plugin.get_config()
            max_len = _clamp_max_content_length(config.get("max_content_length"))
            language = config.get("language", "zh_Hans")

            # Get model
            model_uuid = config.get("model")
            if not model_uuid:
                models = await plugin.get_llm_models()
                if not models:
                    await event_context.reply(platform_message.MessageChain([
                        platform_message.Plain(text="⚠️ 没有可用的 LLM 模型，无法生成摘要。")
                    ]))
                    return
                model_uuid = models[0]

            for url in unique_urls:
                try:
                    title, content = await plugin.fetch_page(url, max_len)

                    if len(content) < 50:
                        continue

                    summary = await plugin.summarize(url, title, content, model_uuid, language)

                    reply_text = f"📄 {title}\n\n{summary}"
                    await event_context.reply(platform_message.MessageChain([
                        platform_message.Plain(text=reply_text)
                    ]))

                except Exception as e:
                    logger.warning(
                        f"Failed to summarize {_redact_url(url)}: {_redact_text(str(e))}"
                    )

        except Exception as e:
            logger.error(
                "Error in _handle_message: "
                f"{_redact_text(str(e))}\n{_redact_text(traceback.format_exc())}"
            )
