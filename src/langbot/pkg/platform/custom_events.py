from __future__ import annotations

import typing

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session


class MessageRecalled(platform_events.Event):
    """Platform-level recall event emitted by adapters."""

    type: str = 'MessageRecalled'

    message_id: typing.Union[int, str]
    chat_id: str = ''
    recall_time: str = ''
    recall_type: str = ''

    launcher_type: provider_session.LauncherTypes
    launcher_id: typing.Union[int, str]
    sender_id: typing.Union[int, str]

    message_event: platform_events.MessageEvent
    message_chain: platform_message.MessageChain
