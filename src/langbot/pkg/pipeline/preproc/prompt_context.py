"""Project turn-scoped system context added by prompt preprocessing hooks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PREPROCESSED_SYSTEM_CONTEXT = '_host_prompt_preprocessing_system_context'


def system_messages(messages: list[Any] | None) -> list[dict[str, Any]]:
    """Snapshot system messages without retaining mutable plugin/history objects."""

    result = []
    for message in messages or []:
        value = message.model_dump(mode='json') if hasattr(message, 'model_dump') else message
        if isinstance(value, dict) and value.get('role') == 'system':
            result.append(deepcopy(value))
    return result


def added_system_context(original: list[dict[str, Any]], messages: list[Any] | None) -> list[dict[str, Any]]:
    """Return new or modified system messages in the hook's final order.

    Existing history remains available through the transcript API. Matching each
    original occurrence prevents it from also being inserted through GET_PROMPT.
    """

    remaining = list(original)
    added = []
    for message in system_messages(messages):
        if message in remaining:
            remaining.remove(message)
        else:
            added.append(message)
    return added
