"""Web Page Bot adapter - lightweight adapter for embeddable chat widget"""

import typing

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class WebPageBotAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Lightweight adapter for the embeddable page bot.

    This adapter does not handle messages itself. The actual WebSocket
    communication is handled by the singleton websocket_proxy_bot.
    This adapter stores event listeners so that RuntimeBot can register
    its handlers, which are then called by the websocket adapter when
    a message arrives for this bot's pipeline.
    """

    listeners: dict = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(config=config, logger=logger, **kwargs)
        self.listeners = {}

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict:
        return {}

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        return {}

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        return {}

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable,
    ):
        self.listeners[event_type] = func

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable,
    ):
        self.listeners.pop(event_type, None)

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def run_async(self):
        pass

    async def kill(self):
        pass
