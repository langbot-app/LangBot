from __future__ import annotations

import abc
import typing

import langbot_plugin.api.entities.builtin.platform.message as platform_message


class AbstractEventLogger(abc.ABC):
    """This is the interface for all event loggers.

    langbot plugin sdk will implement the proxy class for plugin to use.
    langbot will implement the real logger class.
    """

    @abc.abstractmethod
    async def info(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    @abc.abstractmethod
    async def debug(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    @abc.abstractmethod
    async def warning(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        pass

    @abc.abstractmethod
    async def error(
        self,
        text: str,
        images: typing.Optional[list[platform_message.Image]] = None,
        message_session_id: typing.Optional[str] = None,
        no_throw: bool = True,
    ):
        pass
