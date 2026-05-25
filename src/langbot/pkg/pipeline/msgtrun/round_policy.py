"""Shared max-round message window helpers for Pipeline behavior."""
from __future__ import annotations

import typing


DEFAULT_MAX_ROUND = 10


def get_max_round(config: dict[str, typing.Any]) -> typing.Any:
    """Return the configured Pipeline max-round value."""
    return config.get('max-round', DEFAULT_MAX_ROUND)


def select_max_round_messages(
    messages: list[typing.Any] | None,
    max_round: typing.Any,
) -> list[typing.Any]:
    """Select a bounded recent message window by user-round count."""
    if not messages:
        return []

    temp_messages: list[typing.Any] = []
    current_round = 0

    for msg in messages[::-1]:
        if current_round < max_round:
            temp_messages.append(msg)
            if getattr(msg, 'role', None) == 'user':
                current_round += 1
        else:
            break

    return temp_messages[::-1]
