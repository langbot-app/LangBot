"""Convert authenticated Harness frames into standard message events."""

import hashlib
import json
import time
import typing
import uuid

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def harness_session_id(workspace_uuid: str, account_uuid: str, processor_uuid: str, conversation_id: str) -> str:
    scope = json.dumps([workspace_uuid, account_uuid, processor_uuid, conversation_id], separators=(',', ':'))
    return 'harness-v1-' + hashlib.sha256(scope.encode()).hexdigest()


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
    raw_content = frame.get('content')
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('conversation_id is required')
    if isinstance(raw_content, str):
        message_text, attachments = raw_content, []
    elif isinstance(raw_content, dict) and isinstance(raw_content.get('text'), str):
        message_text = raw_content['text']
        attachments = raw_content.get('attachments', [])
        if not isinstance(attachments, list) or len(attachments) > 10:
            raise ValueError('invalid attachments')
    else:
        raise ValueError('content must be text or structured content')
    account_uuid = identity.get('account_uuid')
    display_name = identity.get('display_name')
    if not account_uuid or not display_name:
        raise ValueError('authenticated account identity is required')

    timestamp = time.time()
    session_id = harness_session_id(workspace_uuid, account_uuid, processor_uuid, conversation_id)
    source = {
        'harness_conversation_id': conversation_id,
        'harness_session_id': session_id,
        'harness_connection_id': connection_id,
        'harness_processor_uuid': processor_uuid,
    }
    sender = platform_entities.User(id=account_uuid, nickname=display_name, remark=identity.get('email', ''))
    components: list[platform_message.MessageComponent] = [platform_message.Plain(text=message_text)]
    for attachment in attachments:
        if not isinstance(attachment, dict) or not isinstance(attachment.get('dataUrl'), str):
            raise ValueError('invalid attachment')
        data = attachment['dataUrl']
        if len(data) > 14_000_000:
            raise ValueError('attachment too large')
        mime = attachment.get('mimeType') if isinstance(attachment.get('mimeType'), str) else 'application/octet-stream'
        name = attachment.get('name') if isinstance(attachment.get('name'), str) else 'attachment'
        if mime.startswith('image/'):
            components.append(platform_message.Image(base64=data))
        else:
            components.append(platform_message.File(name=name, size=int(attachment.get('size', 0) or 0), base64=data))
    legacy = platform_events.FriendMessage(
        sender=platform_entities.Friend(id=account_uuid, nickname=display_name, remark=identity.get('email', '')),
        message_chain=platform_message.MessageChain(components),
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
