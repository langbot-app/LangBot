"""User-facing bot configuration errors without credentials or validation inputs."""

import json

import pydantic

from .secrets import redact_secrets


class BotApplyError(Exception):
    """Configuration was persisted, but the runtime could not apply it."""

    def __init__(self, message: str, bot_uuid: str | None = None):
        super().__init__(message)
        self.bot_uuid = bot_uuid


def bot_error_message(error: Exception, configuration: dict) -> str:
    if isinstance(error, pydantic.ValidationError):
        text = '; '.join(
            f'{".".join(map(str, item["loc"]))}: {item["msg"]}'
            for item in error.errors(include_input=False, include_context=False, include_url=False)
        )
    else:
        text = str(error).strip() or type(error).__name__

    replacements = []

    def collect(original, masked):
        if isinstance(original, dict) and isinstance(masked, dict):
            for key, value in original.items():
                collect(value, masked.get(key))
        elif isinstance(original, (list, tuple)) and isinstance(masked, (list, tuple)):
            for value, replacement in zip(original, masked):
                collect(value, replacement)
        elif isinstance(original, str) and original and original != masked:
            for representation in {original, repr(original)[1:-1], json.dumps(original, ensure_ascii=False)[1:-1]}:
                replacements.append((representation, str(masked)))

    collect(configuration, redact_secrets(configuration))
    for original, masked in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(original, masked)
    return text[:2000]
