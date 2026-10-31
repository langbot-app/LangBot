from __future__ import annotations

import logging
import traceback

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


logger = logging.getLogger("AutoTranslate.translator")


class Translator(EventListener):
    """Detects foreign language messages and auto-translates them."""

    def __init__(self):
        super().__init__()

        @self.handler(events.GroupMessageReceived)
        async def on_group_message(event_context: context.EventContext):
            await self._handle_message(event_context, is_group=True)

        @self.handler(events.PersonMessageReceived)
        async def on_person_message(event_context: context.EventContext):
            await self._handle_message(event_context, is_group=False)

    async def _handle_message(self, event_context: context.EventContext, is_group: bool):
        try:
            plugin = self.plugin
            config = plugin.get_config()

            # Check if private chat translation is enabled
            if not is_group and not config.get("enable_private", False):
                return

            event = event_context.event

            # Extract plain text
            text_parts = []
            for component in event.message_chain:
                if isinstance(component, platform_message.Plain):
                    text_parts.append(component.text)

            text = "".join(text_parts).strip()
            if not text:
                return

            # Skip short messages
            min_len = config.get("min_text_length", 4)
            if len(text) < min_len:
                return

            # Get target language
            target_lang = config.get("target_language", "zh_Hans")

            # Get model
            model_uuid = config.get("model")
            if not model_uuid:
                models = await plugin.get_llm_models()
                if not models:
                    return
                model_uuid = models[0]

            # Detect and translate
            translation = await plugin.translate(text, model_uuid, target_lang)

            if translation is None:
                # Already in target language, no action
                return

            # Reply with translation (don't block default pipeline)
            reply_text = f"🌐 {translation}"
            await event_context.reply(platform_message.MessageChain([
                platform_message.Plain(text=reply_text)
            ]))

        except Exception as e:
            logger.error(f"Error in translator: {e}\n{traceback.format_exc()}")
