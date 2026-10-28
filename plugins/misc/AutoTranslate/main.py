from __future__ import annotations

import logging

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.entities.builtin.provider.message import Message, ContentElement

logger = logging.getLogger("AutoTranslate")

LANG_NAMES = {
    "zh_Hans": "简体中文",
    "en_US": "English",
    "ja_JP": "日本語",
    "ko_KR": "한국어",
    "fr_FR": "Français",
    "es_ES": "Español",
}

DETECT_AND_TRANSLATE_PROMPT = """You are a language detection and translation assistant.

Given the following message, determine if it is written in {target_lang_name}.

- If the message IS already in {target_lang_name}, respond with EXACTLY: __NO_TRANSLATE__
- If the message is in a DIFFERENT language, translate it into {target_lang_name} naturally and fluently. Only output the translation, nothing else.
- For very short messages (single words, emoticons, numbers, URLs), respond with: __NO_TRANSLATE__
- For mixed-language messages where the majority is already in {target_lang_name}, respond with: __NO_TRANSLATE__

Message:
{text}"""


class AutoTranslate(BasePlugin):
    """Auto-detect and translate foreign language messages using LLM."""

    def __init__(self):
        super().__init__()

    async def initialize(self):
        logger.info("AutoTranslate plugin initialized")

    async def translate(self, text: str, model_uuid: str, target_lang: str) -> str | None:
        """Detect language and translate if needed. Returns translated text or None if no translation needed."""
        target_lang_name = LANG_NAMES.get(target_lang, target_lang)

        prompt = DETECT_AND_TRANSLATE_PROMPT.format(
            target_lang_name=target_lang_name,
            text=text,
        )

        msg = Message(
            role="user",
            content=[ContentElement.from_text(prompt)],
        )

        response = await self.invoke_llm(
            messages=[msg],
            llm_model_uuid=model_uuid,
        )

        result = ""
        if isinstance(response.content, str):
            result = response.content.strip()
        elif isinstance(response.content, list):
            parts = [e.text for e in response.content if hasattr(e, "text") and e.text]
            result = "\n".join(parts).strip()

        if not result or "__NO_TRANSLATE__" in result:
            return None

        return result
