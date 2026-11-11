from __future__ import annotations

# Platform adapter abstract base classes
import typing
import abc
import pydantic

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionDeliveryCapabilities,
    InteractionHandle,
    InteractionRequest,
    InteractionSubmission,
)


class AbstractMessagePlatformAdapter(pydantic.BaseModel, metaclass=abc.ABCMeta):
    """Message platform adapter base class."""

    bot_account_id: str = pydantic.Field(default="")
    """Bot account ID, should be set during initialization."""

    config: dict

    logger: abstract_platform_logger.AbstractEventLogger = pydantic.Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_supported_apis(self) -> list[str]:
        """Expose the message APIs required of every legacy adapter to Agents."""
        return ["send_message", "reply_message"]

    @abc.abstractmethod
    async def send_message(
        self, target_type: str, target_id: str, message: platform_message.MessageChain
    ):
        """Send a message proactively.

        Args:
            target_type: Target type, 'person' or 'group'.
            target_id: Target ID.
            message: Message chain to send.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to a message.

        Args:
            message_source: The source message event to reply to.
            message: Message chain to send.
            quote_origin: Whether to quote the original message. Defaults to False.
        """
        raise NotImplementedError

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """Reply to a message (streaming output).

        Args:
            message_source: The source message event.
            bot_message: Bot message context.
            message: Message chain to send.
            quote_origin: Whether to quote the original message. Defaults to False.
            is_final: Whether this is the final chunk. Defaults to False.
        """
        raise NotImplementedError

    async def create_message_card(
        self, message_id: typing.Type[str, int], event: platform_events.MessageEvent
    ) -> bool:
        """Create a card message placeholder for streaming.

        Args:
            message_id: Message ID.
            event: The source message event.
        """
        return False

    async def is_muted(self, group_id: int) -> bool:
        """Check if the bot is muted in the specified group."""
        return False

    @abc.abstractmethod
    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, AbstractMessagePlatformAdapter], None
        ],
    ):
        """Register an event listener.

        Args:
            event_type: The event type to listen for.
            callback: Callback function that receives the event and adapter.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, AbstractMessagePlatformAdapter], None
        ],
    ):
        """Unregister an event listener.

        Args:
            event_type: The event type to stop listening for.
            callback: The callback to remove.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def run_async(self):
        """Start the adapter asynchronously."""
        raise NotImplementedError

    async def is_stream_output_supported(self) -> bool:
        """Check if streaming output is supported."""
        return False

    @abc.abstractmethod
    async def kill(self) -> bool:
        """Shut down the adapter.

        Returns:
            True if shutdown succeeded. On hot-reload, returning False
            prevents the underlying MessageSource from being reloaded.
        """
        raise NotImplementedError


class AbstractPlatformAdapter(AbstractMessagePlatformAdapter):
    """Platform adapter base class (EBA version).

    Compared to the legacy AbstractMessagePlatformAdapter:
    - Adds universal API methods (edit_message, delete_message, get_group_info, etc.)
    - Adds pass-through API (call_platform_api)
    - Adds capability declaration (get_supported_events, get_supported_apis)
    - Event listeners support all event types, not just message events
    """

    # ---- Capability Declaration ----

    def get_supported_events(self) -> list[str]:
        """Return the list of event types supported by this adapter."""
        return ["message.received"]

    def get_supported_apis(self) -> list[str]:
        """Return the list of APIs supported by this adapter."""
        apis = ["send_message", "reply_message"]
        if type(self).send_interaction is not AbstractPlatformAdapter.send_interaction:
            apis.append("send_interaction")
            apis.append("get_interaction_capabilities")
        if (
            type(self).update_interaction
            is not AbstractPlatformAdapter.update_interaction
        ):
            apis.append("update_interaction")
        return apis

    def get_interaction_capabilities(self) -> InteractionDeliveryCapabilities:
        """Return native interaction capabilities; empty means no native cards."""
        return InteractionDeliveryCapabilities()

    async def send_interaction(
        self,
        target_type: str,
        target_id: str,
        request: InteractionRequest,
        callback_token: str,
        reply_to: str | None = None,
    ) -> InteractionHandle:
        raise NotSupportedError("send_interaction")

    async def update_interaction(
        self,
        handle: InteractionHandle,
        state: typing.Literal["submitted", "expired", "cancelled"],
        submission: InteractionSubmission | None = None,
    ) -> InteractionHandle:
        raise NotSupportedError("update_interaction")

    # ---- Optional Message Methods ----

    async def edit_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        new_content: platform_message.MessageChain,
    ) -> None:
        """Edit a previously sent message."""
        raise NotSupportedError("edit_message")

    async def delete_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> None:
        """Delete / recall a message."""
        raise NotSupportedError("delete_message")

    async def forward_message(
        self,
        from_chat_type: str,
        from_chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
        to_chat_type: str,
        to_chat_id: typing.Union[int, str],
    ) -> platform_events.MessageResult:
        """Forward a message."""
        raise NotSupportedError("forward_message")

    async def get_message(
        self,
        chat_type: str,
        chat_id: typing.Union[int, str],
        message_id: typing.Union[int, str],
    ) -> platform_events.MessageReceivedEvent:
        """Retrieve a specific message."""
        raise NotSupportedError("get_message")

    # ---- Optional Group Methods ----

    async def get_group_info(
        self,
        group_id: typing.Union[int, str],
    ) -> platform_entities.UserGroup:
        """Get group information."""
        raise NotSupportedError("get_group_info")

    async def get_group_list(self) -> list[platform_entities.UserGroup]:
        """Get the list of groups the bot has joined."""
        raise NotSupportedError("get_group_list")

    async def get_group_member_list(
        self,
        group_id: typing.Union[int, str],
    ) -> list[platform_entities.UserGroupMember]:
        """Get the member list of a group."""
        raise NotSupportedError("get_group_member_list")

    async def get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> platform_entities.UserGroupMember:
        """Get information about a specific group member."""
        raise NotSupportedError("get_group_member_info")

    async def set_group_name(
        self,
        group_id: typing.Union[int, str],
        name: str,
    ) -> None:
        """Set the group name."""
        raise NotSupportedError("set_group_name")

    async def mute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        duration: int = 0,
    ) -> None:
        """Mute a group member."""
        raise NotSupportedError("mute_member")

    async def unmute_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """Unmute a group member."""
        raise NotSupportedError("unmute_member")

    async def kick_member(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
    ) -> None:
        """Kick a member from the group."""
        raise NotSupportedError("kick_member")

    async def leave_group(
        self,
        group_id: typing.Union[int, str],
    ) -> None:
        """Make the bot leave a group."""
        raise NotSupportedError("leave_group")

    # ---- Optional User Methods ----

    async def get_user_info(
        self,
        user_id: typing.Union[int, str],
    ) -> platform_entities.User:
        """Get user information."""
        raise NotSupportedError("get_user_info")

    async def get_friend_list(self) -> list[platform_entities.User]:
        """Get the bot's friend list."""
        raise NotSupportedError("get_friend_list")

    async def approve_friend_request(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
        remark: typing.Optional[str] = None,
    ) -> None:
        """Handle a friend request."""
        raise NotSupportedError("approve_friend_request")

    async def approve_group_invite(
        self,
        request_id: typing.Union[int, str],
        approve: bool = True,
    ) -> None:
        """Handle a group invitation."""
        raise NotSupportedError("approve_group_invite")

    # ---- Optional Media Methods ----

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
    ) -> str:
        """Upload a file. Returns file ID or URL."""
        raise NotSupportedError("upload_file")

    async def get_file_url(
        self,
        file_id: str,
    ) -> str:
        """Get a file download URL."""
        raise NotSupportedError("get_file_url")

    # ---- Pass-through API ----

    async def call_platform_api(
        self,
        action: str,
        params: dict = {},
    ) -> dict:
        """Call an adapter-specific platform API."""
        raise NotSupportedError("call_platform_api")


class AbstractMessageConverter:
    """Message chain converter base class."""

    @staticmethod
    def yiri2target(message_chain: platform_message.MessageChain):
        """Convert internal message chain to platform-specific format.

        Args:
            message_chain: Internal message chain.

        Returns:
            Platform-specific message representation.
        """
        raise NotImplementedError

    @staticmethod
    def target2yiri(message_chain: typing.Any) -> platform_message.MessageChain:
        """Convert platform-specific message to internal message chain.

        Args:
            message_chain: Platform-specific message.

        Returns:
            Internal message chain.
        """
        raise NotImplementedError


class AbstractEventConverter:
    """Event converter base class."""

    @staticmethod
    def yiri2target(event: typing.Type[platform_events.Event]):
        """Convert internal event to platform-specific event.

        Args:
            event: Internal event.

        Returns:
            Platform-specific event.
        """
        raise NotImplementedError

    @staticmethod
    def target2yiri(event: typing.Any) -> platform_events.Event:
        """Convert platform-specific event to internal event.

        Args:
            event: Platform-specific event.

        Returns:
            Internal event.
        """
        raise NotImplementedError
