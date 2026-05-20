"""
Fake platform factory for tests.

Provides a fake platform adapter for tests that need inbound message injection
and outbound message capture.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities


class FakePlatform:
    """Fake platform adapter for unit and integration tests.

    Simulates platform behavior without real network calls:
    - Inbound text message construction
    - Group and private conversation identities
    - Mention-bot flag
    - Outbound text capture
    - Outbound file/image capture
    - Send failure simulation

    Does not start real platform adapters.
    Does not call IM platform SDKs.
    """

    def __init__(
        self,
        *,
        bot_account_id: str = "test-bot",
        stream_output_supported: bool = False,
        raise_error: Exception = None,
    ):
        self.bot_account_id = bot_account_id
        self._stream_output_supported = stream_output_supported
        self._raise_error = raise_error

        # Captured outbound messages
        self._outbound_messages: list[dict] = []
        self._outbound_chunks: list[dict] = []

        # Registered listeners
        self._listeners: dict = {}

    def raises(self, error: Exception) -> "FakePlatform":
        """Configure platform to raise an error on send."""
        self._raise_error = error
        return self

    def send_failure(self) -> "FakePlatform":
        """Configure platform to simulate send failure."""
        return self.raises(Exception("Platform send failure"))

    def supports_streaming(self, supported: bool = True) -> "FakePlatform":
        """Configure whether streaming output is supported."""
        self._stream_output_supported = supported
        return self

    def get_outbound_messages(self) -> list[dict]:
        """Get all captured outbound messages for assertions."""
        return self._outbound_messages.copy()

    def get_outbound_chunks(self) -> list[dict]:
        """Get all captured outbound streaming chunks for assertions."""
        return self._outbound_chunks.copy()

    def clear_outbound(self):
        """Clear captured outbound messages."""
        self._outbound_messages.clear()
        self._outbound_chunks.clear()

    def last_message(self) -> dict | None:
        """Get the last captured outbound message."""
        return self._outbound_messages[-1] if self._outbound_messages else None

    def last_chunk(self) -> dict | None:
        """Get the last captured streaming chunk."""
        return self._outbound_chunks[-1] if self._outbound_chunks else None

    # ============== Inbound Message Construction ==============

    def create_friend_message(
        self,
        text: str,
        sender_id: typing.Union[int, str] = 12345,
        nickname: str = "TestUser",
    ) -> platform_events.FriendMessage:
        """Create an inbound friend (private) message event."""
        sender = platform_entities.Friend(
            id=sender_id,
            nickname=nickname,
            remark=None,
        )
        chain = platform_message.MessageChain([
            platform_message.Plain(text=text),
        ])
        return platform_events.FriendMessage(
            type="FriendMessage",
            sender=sender,
            message_chain=chain,
            time=1609459200,
        )

    def create_group_message(
        self,
        text: str,
        sender_id: typing.Union[int, str] = 12345,
        sender_name: str = "TestUser",
        group_id: typing.Union[int, str] = 99999,
        group_name: str = "TestGroup",
        mention_bot: bool = False,
    ) -> platform_events.GroupMessage:
        """Create an inbound group message event.

        Args:
            text: Message text content
            sender_id: Sender user ID
            sender_name: Sender display name
            group_id: Group ID
            group_name: Group name
            mention_bot: If True, prepend @mention of bot account
        """
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

        # Build message chain with optional mention
        components = []
        if mention_bot:
            components.append(platform_message.At(target=self.bot_account_id))
            components.append(platform_message.Plain(text=" "))
        components.append(platform_message.Plain(text=text))

        chain = platform_message.MessageChain(components)
        return platform_events.GroupMessage(
            type="GroupMessage",
            sender=sender,
            message_chain=chain,
            time=1609459200,
        )

    def create_image_message(
        self,
        url: str = "https://example.com/image.png",
        text: str = "",
        sender_id: typing.Union[int, str] = 12345,
        is_group: bool = False,
        group_id: typing.Union[int, str] = 99999,
    ) -> platform_events.MessageEvent:
        """Create an inbound image message event."""
        components = []
        if text:
            components.append(platform_message.Plain(text=text))
        components.append(platform_message.Image(url=url))
        chain = platform_message.MessageChain(components)

        if is_group:
            return self.create_group_message("", sender_id, group_id=group_id)
            # Replace chain
        else:
            sender = platform_entities.Friend(id=sender_id, nickname="TestUser", remark=None)
            return platform_events.FriendMessage(
                type="FriendMessage",
                sender=sender,
                message_chain=chain,
                time=1609459200,
            )

    # ============== Adapter Methods (Simulated) ==============

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ):
        """Simulate sending a message (captures for assertions)."""
        if self._raise_error:
            raise self._raise_error

        self._outbound_messages.append({
            "type": "send",
            "target_type": target_type,
            "target_id": target_id,
            "message": message,
        })

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Simulate replying to a message (captures for assertions)."""
        if self._raise_error:
            raise self._raise_error

        self._outbound_messages.append({
            "type": "reply",
            "source_type": message_source.type,
            "source": message_source,
            "message": message,
            "quote_origin": quote_origin,
        })

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """Simulate streaming reply (captures for assertions)."""
        if self._raise_error:
            raise self._raise_error

        self._outbound_chunks.append({
            "type": "reply_chunk",
            "source_type": message_source.type,
            "source": message_source,
            "bot_message": bot_message,
            "message": message,
            "quote_origin": quote_origin,
            "is_final": is_final,
        })

    async def is_stream_output_supported(self) -> bool:
        """Return whether streaming output is supported."""
        return self._stream_output_supported

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable,
    ):
        """Register an event listener (stores for simulation)."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable,
    ):
        """Unregister an event listener."""
        if event_type in self._listeners:
            self._listeners[event_type].remove(callback)

    async def run_async(self):
        """Simulate running the adapter (does nothing)."""
        pass

    async def kill(self) -> bool:
        """Simulate killing the adapter."""
        return True

    async def is_muted(self, group_id: int) -> bool:
        """Simulate checking mute status."""
        return False

    async def create_message_card(
        self,
        message_id: typing.Type[str, int],
        event: platform_events.MessageEvent,
    ) -> bool:
        """Simulate creating a message card."""
        return False

    # ============== Simulation Helpers ==============

    async def simulate_inbound_event(
        self,
        event: platform_events.Event,
    ):
        """Simulate receiving an inbound event by calling registered listeners."""
        listeners = self._listeners.get(type(event), [])
        for callback in listeners:
            await callback(event, self)


def fake_platform(
    bot_account_id: str = "test-bot",
    stream_output_supported: bool = False,
) -> FakePlatform:
    """Create a FakePlatform instance."""
    return FakePlatform(
        bot_account_id=bot_account_id,
        stream_output_supported=stream_output_supported,
    )


def fake_platform_with_streaming() -> FakePlatform:
    """Create a FakePlatform that supports streaming output."""
    return FakePlatform(stream_output_supported=True)


def fake_platform_with_failure() -> FakePlatform:
    """Create a FakePlatform that simulates send failure."""
    return FakePlatform().send_failure()


# ============== Mock Adapter (for Query) ==============


def mock_platform_adapter(platform: FakePlatform = None) -> Mock:
    """Create a mock platform adapter using FakePlatform or a simple mock."""
    if platform is None:
        platform = FakePlatform()

    adapter = Mock()
    adapter.bot_account_id = platform.bot_account_id
    adapter.reply_message = AsyncMock(side_effect=platform.reply_message)
    adapter.reply_message_chunk = AsyncMock(side_effect=platform.reply_message_chunk)
    adapter.send_message = AsyncMock(side_effect=platform.send_message)
    adapter.is_stream_output_supported = AsyncMock(
        return_value=platform._stream_output_supported
    )
    adapter._fake_platform = platform  # Store for assertions

    return adapter