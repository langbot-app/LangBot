"""Convert authenticated Harness frames into standard message events."""

import hashlib
import json
import time
import typing
import uuid

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def build_event(
    frame: dict[str, typing.Any],
    identity: dict[str, str],
    *,
    workspace_uuid: str,
    processor_uuid: str,
    connection_id: str,
) -> platform_events.MessageReceivedEvent:
    """Build the EBA event and its legacy-compatible source metadata."""
    conversation_id = frame.get('conversation_id')
    message_text = frame.get('content')
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('conversation_id is required')
    if not isinstance(message_text, str):
        raise ValueError('content must be a string')
    account_uuid = identity.get('account_uuid')
    display_name = identity.get('display_name')
    if not account_uuid or not display_name:
        raise ValueError('authenticated account identity is required')

    timestamp = time.time()
    scope = json.dumps([workspace_uuid, account_uuid, processor_uuid, conversation_id], separators=(',', ':'))
    session_id = 'harness-v1-' + hashlib.sha256(scope.encode()).hexdigest()
    source = {
        'harness_conversation_id': conversation_id,
        'harness_session_id': session_id,
        'harness_connection_id': connection_id,
        'harness_processor_uuid': processor_uuid,
    }
    sender = platform_entities.User(id=account_uuid, nickname=display_name, remark=identity.get('email', ''))
    legacy = platform_events.FriendMessage(
        sender=platform_entities.Friend(id=account_uuid, nickname=display_name, remark=identity.get('email', '')),
        message_chain=platform_message.MessageChain([platform_message.Plain(text=message_text)]),
        time=timestamp,
        source_platform_object=source,
    )
    return platform_events.MessageReceivedEvent(
        type='message.received',
        timestamp=timestamp,
        adapter_name='harness-omni',
        message_id=str(uuid.uuid4()),
        message_chain=legacy.message_chain,
        sender=sender,
        chat_type=platform_entities.ChatType.PRIVATE,
        chat_id=session_id,
        legacy_event=legacy,
        source_platform_object=source,
    )
