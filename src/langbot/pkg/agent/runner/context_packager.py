"""Agent context packaging helpers."""
from __future__ import annotations

import dataclasses
import typing

from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query


DEFAULT_LEGACY_MAX_ROUND = 10


@dataclasses.dataclass(frozen=True)
class ContextPackagingResult:
    """Packaged working context for one AgentRunner run."""

    messages: list[typing.Any]
    policy: dict[str, typing.Any]
    history: dict[str, typing.Any]


def get_legacy_max_round(runner_config: dict[str, typing.Any]) -> typing.Any:
    """Return the configured legacy max-round value.

    Keep the existing config semantics intact: callers are expected to pass the
    already-resolved runner binding config, and invalid values fail the same way
    the old truncator failed when comparing them with an integer round count.
    """
    return runner_config.get('max-round', DEFAULT_LEGACY_MAX_ROUND)


def select_legacy_max_round_messages(
    messages: list[typing.Any] | None,
    max_round: typing.Any,
) -> list[typing.Any]:
    """Select the same message window as the legacy round truncator."""
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


class AgentContextPackager:
    """Build the bounded working context for AgentRunner execution."""

    def package_messages(
        self,
        query: pipeline_query.Query,
        runner_config: dict[str, typing.Any],
    ) -> ContextPackagingResult:
        """Package query messages using the current legacy max-round policy."""
        source_messages = query.messages or []
        max_round = get_legacy_max_round(runner_config)
        packaged_messages = select_legacy_max_round_messages(source_messages, max_round)

        return ContextPackagingResult(
            messages=packaged_messages,
            policy={
                'mode': 'legacy_max_round',
                'max_round': max_round,
            },
            history={
                'source': 'query.messages',
                'source_total_count': len(source_messages),
                'delivered_count': len(packaged_messages),
                'messages_complete': len(packaged_messages) == len(source_messages),
            },
        )
