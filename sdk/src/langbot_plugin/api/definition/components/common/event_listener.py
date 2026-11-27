from __future__ import annotations

from typing import Callable, Coroutine, Any

import pydantic

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.events import BaseEventModel
from langbot_plugin.api.entities.context import EventContext


class EventListener(BaseComponent):
    """The event listener component."""

    __kind__ = "EventListener"

    registered_handlers: dict[
        type[BaseEventModel], list[Callable[[EventContext], Coroutine[Any, Any, None]]]
    ] = pydantic.Field(default_factory=dict)

    def __init__(self):
        self.registered_handlers = {}

    def handler(
        self,
        event_type: type[BaseEventModel],
    ) -> Callable[
        [Callable[[EventContext], Coroutine[Any, Any, None]]],
        Callable[[EventContext], Coroutine[Any, Any, None]],
    ]:
        """Register a handler for the event."""

        def decorator(
            handler: Callable[[EventContext], Coroutine[Any, Any, None]],
        ) -> Callable[[EventContext], Coroutine[Any, Any, None]]:
            if event_type not in self.registered_handlers:
                self.registered_handlers[event_type] = []
            self.registered_handlers[event_type].append(handler)

            return handler

        return decorator
