"""
Message and query factories for tests.

Provides reusable factories for creating message chains, events, and query objects.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
import typing

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.provider.session as provider_session


# Counter for generating unique IDs
_query_counter = 0


def _next_query_id() -> int:
    """Generate a unique query ID."""
    global _query_counter
    _query_counter += 1
    return _query_counter


# ============== Message Chain Factories ==============


def text_chain(text: str = "hello") -> platform_message.MessageChain:
    """Create a simple text message chain."""
    return platform_message.MessageChain([
        platform_message.Plain(text=text),
    ])


def group_text_chain(text: str = "hello") -> platform_message.MessageChain:
    """Create a group text message chain (same as text_chain, context provided by event)."""
    return text_chain(text)


def mention_chain(
    text: str = "hello",
    target: typing.Union[int, str] = 12345,
) -> platform_message.MessageChain:
    """Create a message chain with @mention."""
    return platform_message.MessageChain([
        platform_message.At(target=target),
        platform_message.Plain(text=f" {text}"),
    ])


def image_chain(
    text: str = "",
    url: str = "https://example.com/image.png",
) -> platform_message.MessageChain:
    """Create a message chain with an image."""
    components = []
    if text:
        components.append(platform_message.Plain(text=text))
    components.append(platform_message.Image(url=url))
    return platform_message.MessageChain(components)


def command_chain(
    command: str = "help",
    prefix: str = "/",
) -> platform_message.MessageChain:
    """Create a command message chain."""
    return platform_message.MessageChain([
        platform_message.Plain(text=f"{prefix}{command}"),
    ])


# ============== Message Event Factories ==============


def friend_message_event(
    message_chain: platform_message.MessageChain,
    sender_id: typing.Union[int, str] = 12345,
    nickname: str = "TestUser",
) -> platform_events.FriendMessage:
    """Create a friend (private) message event."""
    sender = platform_entities.Friend(
        id=sender_id,
        nickname=nickname,
        remark=None,
    )
    return platform_events.FriendMessage(
        type="FriendMessage",
        sender=sender,
        message_chain=message_chain,
        time=1609459200,
    )


def group_message_event(
    message_chain: platform_message.MessageChain,
    sender_id: typing.Union[int, str] = 12345,
    sender_name: str = "TestUser",
    group_id: typing.Union[int, str] = 99999,
    group_name: str = "TestGroup",
) -> platform_events.GroupMessage:
    """Create a group message event."""
    group = platform_entities.Group(
        id=group_id,
        name=group_name,
        permission=platform_entities.Permission.Member,
    )
    sender = platform_entities.GroupMember(
        id=sender_id,
        member_name=sender_name,
        permission=platform_entities.Permission.Member,
        group=group,
    )
    return platform_events.GroupMessage(
        type="GroupMessage",
        sender=sender,
        message_chain=message_chain,
        time=1609459200,
    )


# ============== Mock Adapter Factory ==============


def mock_adapter() -> Mock:
    """Create a mock platform adapter."""
    adapter = AsyncMock()
    adapter.is_stream_output_supported = AsyncMock(return_value=False)
    adapter.reply_message = AsyncMock()
    adapter.reply_message_chunk = AsyncMock()
    return adapter


# ============== Query Factories ==============


def _base_query(
    message_chain: platform_message.MessageChain,
    message_event: platform_events.MessageEvent,
    launcher_type: provider_session.LauncherTypes,
    launcher_id: typing.Union[int, str],
    sender_id: typing.Union[int, str],
    adapter: Mock,
    **overrides,
) -> pipeline_query.Query:
    """Create a base query with model_construct to bypass validation."""
    query_id = _next_query_id()

    base_data = {
        "query_id": query_id,
        "launcher_type": launcher_type,
        "launcher_id": launcher_id,
        "sender_id": sender_id,
        "message_chain": message_chain,
        "message_event": message_event,
        "adapter": adapter,
        "pipeline_uuid": "test-pipeline-uuid",
        "bot_uuid": "test-bot-uuid",
        "pipeline_config": {
            "ai": {
                "runner": {"runner": "local-agent"},
                "local-agent": {
                    "model": {"primary": "test-model-uuid", "fallbacks": []},
                    "prompt": "test-prompt",
                },
            },
            "output": {"misc": {"at-sender": False, "quote-origin": False}},
            "trigger": {"misc": {"combine-quote-message": False}},
        },
        "session": None,
        "prompt": None,
        "messages": [],
        "user_message": None,
        "use_funcs": [],
        "use_llm_model_uuid": None,
        "variables": {},
        "resp_messages": [],
        "resp_message_chain": None,
        "current_stage_name": None,
    }

    # Apply overrides
    for key, value in overrides.items():
        base_data[key] = value

    return pipeline_query.Query.model_construct(**base_data)


def text_query(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a basic text query (private chat)."""
    chain = text_chain(text)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def private_text_query(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a private text query (alias for text_query)."""
    return text_query(text, sender_id, **overrides)


def group_text_query(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    group_id: typing.Union[int, str] = 99999,
    **overrides,
) -> pipeline_query.Query:
    """Create a group text query."""
    chain = text_chain(text)
    event = group_message_event(chain, sender_id, group_id=group_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.GROUP,
        launcher_id=group_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def command_query(
    command: str = "help",
    prefix: str = "/",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a command-like query."""
    chain = command_chain(command, prefix)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def mention_query(
    text: str = "hello",
    target: typing.Union[int, str] = 12345,
    sender_id: typing.Union[int, str] = 12345,
    group_id: typing.Union[int, str] = 99999,
    **overrides,
) -> pipeline_query.Query:
    """Create a mention-bot query (group chat with @mention)."""
    chain = mention_chain(text, target)
    event = group_message_event(chain, sender_id, group_id=group_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.GROUP,
        launcher_id=group_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def empty_query(**overrides) -> pipeline_query.Query:
    """Create an empty message query."""
    chain = platform_message.MessageChain([])
    event = friend_message_event(chain)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        adapter=adapter,
        **overrides,
    )


def image_query(
    text: str = "",
    url: str = "https://example.com/image.png",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create an image query."""
    chain = image_chain(text, url)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def file_query(
    url: str = "https://example.com/document.pdf",
    name: str = "document.pdf",
    text: str = "",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a file attachment query."""
    components = []
    if text:
        components.append(platform_message.Plain(text=text))
    components.append(platform_message.File(url=url, name=name))
    chain = platform_message.MessageChain(components)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def unsupported_query(
    unsupported_type: str = "CustomComponent",
    text: str = "",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a query with unsupported/unknown message segment."""
    components = []
    if text:
        components.append(platform_message.Plain(text=text))
    # Use Unknown component for unsupported types
    components.append(platform_message.Unknown(text=f"Unsupported: {unsupported_type}"))
    chain = platform_message.MessageChain(components)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def query_with_session(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    session: provider_session.Session = None,
    **overrides,
) -> pipeline_query.Query:
    """Create a query with a session object.

    If session is None, creates a default session with empty conversation.
    """
    if session is None:
        # Create a default session
        session = provider_session.Session(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id=sender_id,
            sender_id=sender_id,
            use_prompt_name="default",
            using_conversation=None,
            conversations=[],
        )

    return text_query(text, sender_id, session=session, **overrides)


def query_with_config(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    pipeline_config: dict = None,
    **overrides,
) -> pipeline_query.Query:
    """Create a query with custom pipeline configuration.

    If pipeline_config is None, uses default config.
    Useful for testing specific stage behaviors.
    """
    if pipeline_config is None:
        pipeline_config = {
            "ai": {
                "runner": {"runner": "local-agent"},
                "local-agent": {
                    "model": {"primary": "test-model-uuid", "fallbacks": []},
                    "prompt": "test-prompt",
                },
            },
            "output": {"misc": {"at-sender": False, "quote-origin": False}},
            "trigger": {"misc": {"combine-quote-message": False}},
        }

    return text_query(text, sender_id, pipeline_config=pipeline_config, **overrides)


def voice_query(
    url: str = "https://example.com/audio.mp3",
    sender_id: typing.Union[int, str] = 12345,
    **overrides,
) -> pipeline_query.Query:
    """Create a voice/audio query."""
    components = [
        platform_message.Voice(url=url),
    ]
    chain = platform_message.MessageChain(components)
    event = friend_message_event(chain, sender_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=sender_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )


def at_all_query(
    text: str = "hello",
    sender_id: typing.Union[int, str] = 12345,
    group_id: typing.Union[int, str] = 99999,
    **overrides,
) -> pipeline_query.Query:
    """Create a group query with @All mention."""
    components = [
        platform_message.AtAll(),
        platform_message.Plain(text=f" {text}"),
    ]
    chain = platform_message.MessageChain(components)
    event = group_message_event(chain, sender_id, group_id=group_id)
    adapter = mock_adapter()
    return _base_query(
        message_chain=chain,
        message_event=event,
        launcher_type=provider_session.LauncherTypes.GROUP,
        launcher_id=group_id,
        sender_id=sender_id,
        adapter=adapter,
        **overrides,
    )