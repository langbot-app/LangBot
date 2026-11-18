# -*- coding: utf-8 -*-
"""
Platform event models.
"""

import copy
import typing

import pydantic

from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.execution import WorkspaceExecutionScope


class Event(WorkspaceExecutionScope):
    """Base event class.

    Args:
        type: Event type name.
    """

    type: str
    """Event type name."""

    def __repr__(self):
        return (
            self.__class__.__name__
            + "("
            + ", ".join(
                (
                    f"{k}={repr(v)}"
                    for k, v in self.__dict__.items()
                    if k != "type" and v
                )
            )
            + ")"
        )

    @classmethod
    def parse_subtype(cls, obj: dict) -> "Event":
        try:
            return typing.cast(Event, super().parse_obj(obj))
        except ValueError:
            return Event(type=obj["type"])

    @classmethod
    def get_subtype(cls, name: str) -> typing.Type["Event"]:
        try:
            return typing.cast(typing.Type[Event], super().get_subtype(name))  # type: ignore
        except ValueError:
            return Event


###############################
# Legacy Message Events (unchanged)
###############################


class MessageEvent(Event):
    """Message event.

    Args:
        type: Event type name.
        message_chain: Message content.
    """

    type: str
    """Event type name."""
    message_chain: platform_message.MessageChain
    """Message content."""

    time: float | None = None
    """Message timestamp."""

    source_platform_object: typing.Optional[typing.Any] = None
    """Original platform event object.
    For adapter developers: store the raw platform event here so it can be
    retrieved later when replying to the user."""


class FriendMessage(MessageEvent):
    """Private (direct) message.

    Args:
        type: Event type name.
        sender: The friend who sent the message.
        message_chain: Message content.
    """

    type: str = "FriendMessage"
    """Event type name."""
    sender: platform_entities.Friend
    """Message sender."""
    message_chain: platform_message.MessageChain
    """Message content."""

    def model_dump(self, **kwargs):
        return {
            **self.execution_scope_dump(),
            "type": self.type,
            "sender": self.sender.model_dump(),
            "message_chain": self.message_chain.model_dump(),
            "time": self.time,
        }


class GroupMessage(MessageEvent):
    """Group message.

    Args:
        type: Event type name.
        sender: The group member who sent the message.
        message_chain: Message content.
    """

    type: str = "GroupMessage"
    """Event type name."""
    sender: platform_entities.GroupMember
    """Message sender."""
    message_chain: platform_message.MessageChain
    """Message content."""

    @property
    def group(self) -> platform_entities.Group:
        return self.sender.group

    def model_dump(self, **kwargs):
        return {
            **self.execution_scope_dump(),
            "type": self.type,
            "sender": self.sender.model_dump(),
            "message_chain": self.message_chain.model_dump(),
            "time": self.time,
        }


###############################
# Feedback Event
###############################


class FeedbackEvent(Event):
    """User feedback event (like/dislike).

    Fired when a user gives feedback (thumbs up / thumbs down) on an AI Bot
    response.  Currently only supported by the WeChat Work (WeCom) AI Bot
    adapter, but designed to be platform-agnostic so other adapters can adopt
    it in the future.

    Args:
        feedback_id: Unique feedback identifier assigned by the platform.
        feedback_type: ``1`` = like (thumbs up), ``2`` = dislike (thumbs down).
        feedback_content: Optional free-form text the user attached.
        inaccurate_reasons: Optional list of predefined "inaccurate" reason
            tags selected by the user (for dislikes).
        user_id: ID of the user who gave feedback.
        session_id: Session / conversation ID (e.g. ``"person_xxx"`` or
            ``"group_xxx"``).
        message_id: ID of the message being rated.
        stream_id: Stream ID (for streaming responses).
        source_platform_object: Raw platform-specific object, kept for
            adapter-level introspection.
    """

    type: str = "FeedbackEvent"

    feedback_id: str
    """Unique feedback identifier from the platform."""

    feedback_type: int
    """1 = like, 2 = dislike."""

    feedback_content: typing.Optional[str] = None
    """Free-form user feedback text."""

    inaccurate_reasons: typing.Optional[typing.List[str]] = None
    """Predefined inaccuracy reasons (for dislikes)."""

    user_id: typing.Optional[str] = None
    """ID of the user who submitted the feedback."""

    session_id: typing.Optional[str] = None
    """Session / conversation ID."""

    message_id: typing.Optional[str] = None
    """ID of the original message being rated."""

    stream_id: typing.Optional[str] = None
    """Stream message ID (for streaming responses)."""

    source_platform_object: typing.Optional[typing.Any] = None
    """Raw platform event object."""


###############################
# EBA Unified Event System (new)
###############################


class EBAEvent(Event):
    """EBA event base class.

    All unified EBA events inherit from this class.
    Coexists with the legacy MessageEvent hierarchy.
    """

    summary_field: typing.ClassVar[str] = "type"
    """Existing field path used for display summaries; never serialized."""

    type: str
    """Event type identifier, e.g. 'message.received'."""

    timestamp: float = 0.0
    """Event timestamp."""

    bot_uuid: str = ""
    """UUID of the bot that received this event."""

    adapter_name: str = ""
    """Name of the adapter that produced this event."""

    source_platform_object: typing.Optional[typing.Any] = None
    """Raw platform event object for internal adapter use."""


# ---- Message Events ----


class MessageReceivedEvent(EBAEvent):
    """New message received. Replaces legacy FriendMessage / GroupMessage."""

    summary_field: typing.ClassVar[str] = "message_chain"

    type: str = "message.received"

    message_id: typing.Union[int, str] = ""
    """Message ID."""

    message_chain: platform_message.MessageChain = platform_message.MessageChain([])
    """Message content."""

    sender: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    """Message sender."""

    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    """Chat type."""

    chat_id: typing.Union[int, str] = ""
    """Chat ID (user ID for private chats, group ID for group chats)."""

    group: typing.Optional[platform_entities.UserGroup] = None
    """Group info (only present in group chats)."""

    legacy_event: typing.Optional[typing.Union[FriendMessage, GroupMessage]] = (
        pydantic.Field(default=None, exclude=True)
    )
    """Host-only original event retained for lossless legacy adapter round trips."""

    sender_member: typing.Optional[platform_entities.UserGroupMember] = None
    """Group membership details when supplied by the platform."""

    bot_role: typing.Optional[platform_entities.MemberRole] = None
    """Bot role in the current group when supplied by the platform."""

    def to_legacy_event(self) -> typing.Union[FriendMessage, GroupMessage]:
        """Convert this EBA event to a legacy-format event (compatibility layer)."""
        if self.legacy_event is not None:
            return self.legacy_event.model_copy(
                update={
                    "message_chain": self.message_chain,
                    "time": self.timestamp,
                    "source_platform_object": self.source_platform_object,
                }
            )

        permissions = {
            platform_entities.MemberRole.MEMBER: platform_entities.Permission.Member,
            platform_entities.MemberRole.ADMIN: platform_entities.Permission.Administrator,
            platform_entities.MemberRole.OWNER: platform_entities.Permission.Owner,
        }
        if self.chat_type == platform_entities.ChatType.PRIVATE:
            return FriendMessage(
                sender=platform_entities.Friend(
                    id=self.sender.id,
                    nickname=self.sender.nickname,
                    remark=self.sender.remark,
                ),
                message_chain=self.message_chain,
                time=self.timestamp,
                source_platform_object=self.source_platform_object,
            )
        else:
            group = platform_entities.Group(
                id=self.group.id if self.group else self.chat_id,
                name=self.group.name if self.group else "",
                permission=permissions.get(
                    self.bot_role, platform_entities.Permission.Member
                ),
            )
            return GroupMessage(
                sender=platform_entities.GroupMember(
                    id=self.sender.id,
                    member_name=(
                        self.sender_member.display_name if self.sender_member else None
                    )
                    or self.sender.nickname,
                    permission=permissions.get(
                        self.sender_member.role if self.sender_member else None,
                        platform_entities.Permission.Member,
                    ),
                    special_title=(
                        self.sender_member.title if self.sender_member else None
                    )
                    or "",
                    group=group,
                ),
                message_chain=self.message_chain,
                time=self.timestamp,
                source_platform_object=self.source_platform_object,
            )


class MessageEditedEvent(EBAEvent):
    """Message was edited."""

    summary_field: typing.ClassVar[str] = "new_content"

    type: str = "message.edited"

    message_id: typing.Union[int, str] = ""
    """ID of the edited message."""

    new_content: platform_message.MessageChain = platform_message.MessageChain([])
    """New content after editing."""

    editor: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    """User who edited the message."""

    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None


class MessageDeletedEvent(EBAEvent):
    """Message was deleted / recalled."""

    summary_field: typing.ClassVar[str] = "message_id"

    type: str = "message.deleted"

    message_id: typing.Union[int, str] = ""
    """ID of the deleted message."""

    operator: typing.Optional[platform_entities.User] = None
    """User who deleted the message."""

    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None


class MessageReactionEvent(EBAEvent):
    """Message received an emoji reaction."""

    summary_field: typing.ClassVar[str] = "reaction"

    type: str = "message.reaction"

    message_id: typing.Union[int, str] = ""
    """ID of the reacted message."""

    user: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    """User who reacted."""

    reaction: str = ""
    """Reaction emoji identifier."""

    is_add: bool = True
    """True if reaction was added, False if removed."""

    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    chat_id: typing.Union[int, str] = ""
    group: typing.Optional[platform_entities.UserGroup] = None


# ---- Feedback Events ----


class FeedbackReceivedEvent(EBAEvent):
    """User feedback received for a bot response."""

    summary_field: typing.ClassVar[str] = "feedback_content"

    type: str = "feedback.received"

    feedback_id: str
    """Unique feedback identifier from the platform."""

    feedback_type: int
    """1 = like, 2 = dislike, 3 = cancel/remove feedback."""

    feedback_content: typing.Optional[str] = None
    """Free-form user feedback text."""

    inaccurate_reasons: typing.Optional[typing.List[str]] = None
    """Predefined inaccuracy reasons (for dislikes)."""

    user_id: typing.Optional[str] = None
    """ID of the user who submitted the feedback."""

    session_id: typing.Optional[str] = None
    """Session / conversation ID."""

    message_id: typing.Optional[str] = None
    """ID of the original message being rated."""

    stream_id: typing.Optional[str] = None
    """Stream message ID (for streaming responses)."""

    def to_legacy_event(self) -> FeedbackEvent:
        """Convert this EBA event to the legacy FeedbackEvent format."""
        return FeedbackEvent(
            feedback_id=self.feedback_id,
            feedback_type=self.feedback_type,
            feedback_content=self.feedback_content,
            inaccurate_reasons=self.inaccurate_reasons,
            user_id=self.user_id,
            session_id=self.session_id,
            message_id=self.message_id,
            stream_id=self.stream_id,
            source_platform_object=self.source_platform_object,
        )


# ---- Group Events ----


class MemberJoinedEvent(EBAEvent):
    """New member joined a group."""

    summary_field: typing.ClassVar[str] = "member"

    type: str = "group.member_joined"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    """The group."""

    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    """The member who joined."""

    inviter: typing.Optional[platform_entities.User] = None
    """Inviter (if applicable)."""

    join_type: typing.Optional[str] = None
    """How the member joined: 'invite' / 'request' / 'direct' / None."""


class MemberLeftEvent(EBAEvent):
    """Member left a group."""

    summary_field: typing.ClassVar[str] = "member"

    type: str = "group.member_left"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )

    is_kicked: bool = False
    """Whether the member was kicked."""

    operator: typing.Optional[platform_entities.User] = None
    """Operator (the admin who kicked, if applicable)."""


class MemberBannedEvent(EBAEvent):
    """Member was muted / restricted."""

    summary_field: typing.ClassVar[str] = "member"

    type: str = "group.member_banned"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    member: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    duration: typing.Optional[int] = None
    """Mute duration in seconds. None means permanent."""


class GroupInfoUpdatedEvent(EBAEvent):
    """Group info was updated."""

    summary_field: typing.ClassVar[str] = "changed_fields"

    type: str = "group.info_updated"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    """Updated group info."""

    operator: typing.Optional[platform_entities.User] = None
    changed_fields: list[str] = []
    """List of field names that changed."""


# ---- Friend Events ----


class FriendRequestReceivedEvent(EBAEvent):
    """Friend request received."""

    summary_field: typing.ClassVar[str] = "message"

    type: str = "friend.request_received"

    request_id: typing.Union[int, str] = ""
    """Request ID."""

    user: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )
    """The user who sent the request."""

    message: typing.Optional[str] = None
    """Verification message."""


class FriendAddedEvent(EBAEvent):
    """Friend successfully added."""

    summary_field: typing.ClassVar[str] = "user"

    type: str = "friend.added"

    user: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )


class FriendRemovedEvent(EBAEvent):
    """Friend was removed."""

    summary_field: typing.ClassVar[str] = "user"

    type: str = "friend.removed"

    user: platform_entities.User = pydantic.Field(
        default_factory=lambda: platform_entities.User(id="")
    )


# ---- Bot Status Events ----


class BotInvitedToGroupEvent(EBAEvent):
    """Bot was invited to join a group."""

    summary_field: typing.ClassVar[str] = "group"

    type: str = "bot.invited_to_group"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    inviter: typing.Optional[platform_entities.User] = None

    request_id: typing.Optional[typing.Union[int, str]] = None
    """Invitation request ID."""


class BotRemovedFromGroupEvent(EBAEvent):
    """Bot was removed from a group."""

    summary_field: typing.ClassVar[str] = "group"

    type: str = "bot.removed_from_group"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None


class BotMutedEvent(EBAEvent):
    """Bot was muted in a group."""

    summary_field: typing.ClassVar[str] = "group"

    type: str = "bot.muted"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None
    duration: typing.Optional[int] = None


class BotUnmutedEvent(EBAEvent):
    """Bot was unmuted in a group."""

    summary_field: typing.ClassVar[str] = "group"

    type: str = "bot.unmuted"

    group: platform_entities.UserGroup = pydantic.Field(
        default_factory=lambda: platform_entities.UserGroup(id="")
    )
    operator: typing.Optional[platform_entities.User] = None


# ---- Platform-Specific Events ----


class PlatformSpecificEvent(EBAEvent):
    """Platform-specific event.

    Used when the adapter cannot map an event to a standard type.
    """

    summary_field: typing.ClassVar[str] = "action"

    type: str = "platform.specific"

    action: str = ""
    """Platform-specific action identifier."""

    data: dict = {}
    """Event data; structure defined by each adapter."""


class InteractionCallbackEvent(EBAEvent):
    """A platform callback for a Host-owned interaction."""

    summary_field: typing.ClassVar[str] = "callback_token"
    type: str = "interaction.callback"
    callback_token: str
    values: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    action_id: str | None = None
    actor_id: str | None = None
    conversation_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    callback_context: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    raw_submission: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


# ---- WeCom AI Bot Events ----


class WecomBotEnterChatEvent(EBAEvent):
    """User entered an AI bot conversation (not a friend-added event)."""

    summary_field: typing.ClassVar[str] = "chat_id"
    type: str = "wecombot.enter_chat"
    user: typing.Optional[platform_entities.User] = None
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    message_id: str = ""
    data: dict = pydantic.Field(default_factory=dict)


class WecomBotTemplateCardEvent(EBAEvent):
    """User clicked or submitted a non-managed AI bot template card."""

    summary_field: typing.ClassVar[str] = "event_key"
    type: str = "wecombot.template_card_event"
    user: typing.Optional[platform_entities.User] = None
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    message_id: str = ""
    task_id: str = ""
    event_key: str = ""
    card_type: str = ""
    selected_items: list[dict] = pydantic.Field(default_factory=list)
    data: dict = pydantic.Field(default_factory=dict)


class DingTalkCardActionEvent(EBAEvent):
    """A DingTalk card interaction outside managed input forms."""

    summary_field: typing.ClassVar[str] = "action"
    type: str = "dingtalk.card_action"
    user: typing.Optional[platform_entities.User] = None
    space_id: str = ""
    card_instance_id: str = ""
    action: str = ""
    data: dict = pydantic.Field(default_factory=dict)


# ---- WeCom Customer Service Events ----


class WecomCSEnterSessionEvent(EBAEvent):
    """Customer opened a WeCom customer-service conversation."""

    summary_field: typing.ClassVar[str] = "external_userid"
    type: str = "wecomcs.enter_session"
    open_kfid: str = ""
    external_userid: str = ""
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    user: typing.Optional[platform_entities.User] = None
    data: dict = pydantic.Field(default_factory=dict)
    scene: str = ""
    scene_param: str = ""
    welcome_code: str = ""
    wechat_channels: dict = pydantic.Field(default_factory=dict)


class WecomCSMessageSendFailedEvent(EBAEvent):
    """WeCom reported that an outgoing customer-service message failed."""

    summary_field: typing.ClassVar[str] = "fail_msgid"
    type: str = "wecomcs.msg_send_fail"
    open_kfid: str = ""
    external_userid: str = ""
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    user: typing.Optional[platform_entities.User] = None
    data: dict = pydantic.Field(default_factory=dict)
    fail_msgid: str = ""
    fail_type: int = 0


class WecomCSServicerStatusChangedEvent(EBAEvent):
    """A WeCom customer-service representative changed availability."""

    summary_field: typing.ClassVar[str] = "servicer_userid"
    type: str = "wecomcs.servicer_status_change"
    open_kfid: str = ""
    external_userid: str = ""
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    user: typing.Optional[platform_entities.User] = None
    data: dict = pydantic.Field(default_factory=dict)
    servicer_userid: str = ""
    status: int = 0
    stop_type: int = 0


class WecomCSSessionStatusChangedEvent(EBAEvent):
    """A WeCom customer-service conversation was assigned, transferred or closed."""

    summary_field: typing.ClassVar[str] = "external_userid"
    type: str = "wecomcs.session_status_change"
    open_kfid: str = ""
    external_userid: str = ""
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    user: typing.Optional[platform_entities.User] = None
    data: dict = pydantic.Field(default_factory=dict)
    change_type: int = 0
    old_servicer_userid: str = ""
    new_servicer_userid: str = ""
    msg_code: str = ""


class WecomCSRejectCustomerMessageChangedEvent(EBAEvent):
    """A representative enabled or disabled rejection of customer messages."""

    summary_field: typing.ClassVar[str] = "external_userid"
    type: str = "wecomcs.reject_customer_msg_switch_change"
    open_kfid: str = ""
    external_userid: str = ""
    chat_id: str = ""
    chat_type: platform_entities.ChatType = platform_entities.ChatType.PRIVATE
    user: typing.Optional[platform_entities.User] = None
    data: dict = pydantic.Field(default_factory=dict)
    servicer_userid: str = ""
    reject_switch: int = 0


# ---- Message Send Result ----


def event_summary(event: EBAEvent | dict) -> str:
    """Read only the summary field declared by the event class."""
    if isinstance(event, EBAEvent):
        event_type = event.type
        value = getattr(event, event.summary_field, None)
    else:
        event_type = str(event.get("type") or "event")
        event_class = next(
            (
                cls
                for cls in EBAEvent.__subclasses__()
                if cls.model_fields["type"].default == event_type
            ),
            EBAEvent,
        )
        value = event.get(event_class.summary_field)

    def render(value: typing.Any) -> str:
        if value is None:
            return ""
        if isinstance(value, platform_message.MessageChain):
            return str(value)
        if isinstance(value, pydantic.BaseModel):
            value = value.model_dump(mode="json")
        if isinstance(value, dict):
            if "root" in value:
                return render(value["root"])
            if value.get("type") == "Source":
                return ""
            if value.get("type") in {"Plain", "text"}:
                return str(value.get("text") or "")
            if "type" in value:
                return f"[{value['type']}]"
            return str(
                value.get("nickname") or value.get("name") or value.get("id") or ""
            )
        if isinstance(value, (list, tuple)):
            separator = "" if any(isinstance(item, dict) for item in value) else ", "
            return separator.join(render(item) for item in value)
        return str(value)

    return render(value).strip() or event_type


def parse_eba_event(data: dict) -> EBAEvent:
    """Deserialize public EBA event fields without creating plugin-only wrappers."""
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        raise ValueError("An EBA event requires a type")
    for event_class in EBAEvent.__subclasses__():
        if event_class.model_fields["type"].default == data["type"]:
            payload = {
                key: value
                for key, value in data.items()
                if key not in {"legacy_event", "source_platform_object"}
            }
            # Nested Pydantic validation bypasses MessageChain.model_validate,
            # which would erase subtype fields such as Plain.text and Image.url.
            for name, field in event_class.model_fields.items():
                if (
                    field.annotation is platform_message.MessageChain
                    and name in payload
                ):
                    payload[name] = platform_message.MessageChain.model_validate(
                        copy.deepcopy(payload[name])
                    )
            return event_class.model_validate(payload)
    raise ValueError(f"Unknown EBA event type: {data['type']}")


class MessageResult(pydantic.BaseModel):
    """Result of a message send operation."""

    message_id: typing.Optional[typing.Union[int, str]] = None
    """Message ID after successful send."""

    raw: typing.Optional[dict] = None
    """Raw platform response data."""
