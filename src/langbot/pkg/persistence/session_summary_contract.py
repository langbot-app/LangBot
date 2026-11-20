"""Payload-free contracts for interactive conversation lists."""

from dataclasses import dataclass
import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SessionListFilter:
    bot_ids: tuple[str, ...] = ()
    pipeline_ids: tuple[str, ...] = ()
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None
    user_query: str | None = None
    launcher_id: str | None = None
    is_active: bool | None = None


class SessionSummaryReader(Protocol):
    """Read stored summaries without consulting or repairing historical ledgers."""

    async def list_page(
        self, workspace: str, filters: SessionListFilter, limit: int, offset: int
    ) -> tuple[list[dict], int]: ...


@dataclass(frozen=True, slots=True)
class SessionSummaryChange:
    workspace: str
    bot_id: str
    session_id: str
    source_key: str
    timestamp: datetime.datetime
    bot_name: str
    pipeline_id: str = ''
    pipeline_name: str = ''
    platform: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    role: str = 'user'
    event_id: str | None = None


def message_source_key(message_id: str) -> str:
    """Distinct message records remain distinct even when they share an event."""
    return f'message:{message_id}'


def parse_group_member_id(value: str) -> tuple[str, str] | None:
    if not value.startswith('groupmember_'):
        return None
    length, _, payload = value.removeprefix('groupmember_').partition('_')
    if not length.isascii() or not length.isdecimal() or len(length) > len(str(len(payload))):
        return None
    size = int(length)
    sender = payload[size + 1 :]
    if str(size) != length or payload[size : size + 1] != '_' or not sender or sender != sender.strip():
        return None
    return payload[:size], sender


def shares_group_context(config) -> bool:
    ai = config.get('ai') if isinstance(config, dict) else None
    runner = ai.get('runner') if isinstance(ai, dict) else None
    return isinstance(runner, dict) and runner.get('group-context') == 'group'


def conversation_scope(query, launcher=None) -> str:
    launcher = launcher or query
    return build_monitoring_session_id(
        launcher.launcher_type,
        launcher.launcher_id,
        None if shares_group_context(getattr(query, 'pipeline_config', None)) else getattr(query, 'sender_id', None),
    )


def build_monitoring_session_id(
    launcher_type: object,
    launcher_id: object,
    sender_id: object = None,
) -> str:
    """Build the canonical monitoring session ID without altering conversation keys."""
    launcher_type_value = launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)
    if launcher_type_value == 'group' and sender_id is not None:
        sender_text = str(sender_id).strip()
        if sender_text:
            return f'groupmember_{len(str(launcher_id))}_{launcher_id}_{sender_text}'
    return f'{launcher_type_value}_{launcher_id}'


def monitoring_session_id_from_conversation(
    conversation_id: str | None,
    actor_id: object = None,
) -> str:
    """Map a conversation key and optional actor ID to the monitoring session ID."""
    if not conversation_id:
        return ''
    if conversation_id.startswith('group_') and '#' not in conversation_id:
        launcher_id = conversation_id.removeprefix('group_')
        if launcher_id:
            return build_monitoring_session_id('group', launcher_id, actor_id)
    return conversation_id
