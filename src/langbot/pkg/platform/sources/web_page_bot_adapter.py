"""Web Page Bot adapter - lightweight adapter for embeddable chat widget"""

import typing

import pydantic

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

    Message sending/replying is delegated to the websocket_proxy_bot's
    adapter so that replies are actually delivered over the WebSocket
    connection while the dashboard correctly shows this adapter's name.
    """

    listeners: dict = pydantic.Field(default_factory=dict, exclude=True)
    _ws_adapter: typing.Any = None

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(config=config, logger=logger, **kwargs)

    def set_ws_adapter(self, ws_adapter) -> None:
        """Set the underlying WebSocket adapter used for actual message delivery."""
        object.__setattr__(self, '_ws_adapter', ws_adapter)

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> dict:
        if self._ws_adapter is not None:
            return await self._ws_adapter.send_message(target_type, target_id, message)
        return {}

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        if self._ws_adapter is not None:
            return await self._ws_adapter.reply_message(message_source, message, quote_origin)
        return {}

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        if self._ws_adapter is not None:
            return await self._ws_adapter.reply_message_chunk(
                message_source, bot_message, message, quote_origin, is_final
            )
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
