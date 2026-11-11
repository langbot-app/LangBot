from __future__ import annotations

import abc
import typing

from langbot_plugin.api.definition.plugin import BasePlugin
from langbot_plugin.api.proxies.invocation import current_binding, current_config


class BaseComponent(abc.ABC):
    """The abstract base class for all components."""

    plugin: BasePlugin

    def __init__(self):
        pass

    def get_plugin_config(self) -> dict[str, typing.Any]:
        """Return the task-local installation config for stateless components."""

        handler = getattr(getattr(self, "plugin", None), "plugin_runtime_handler", None)
        scoped = current_config(handler)
        if scoped is not None:
            return dict(scoped)
        plugin = getattr(self, "plugin", None)
        return plugin.get_config() if plugin is not None else {}

    def get_installation_binding(self):
        """Return the active installation without storing tenant state on self."""

        handler = getattr(getattr(self, "plugin", None), "plugin_runtime_handler", None)
        return current_binding(handler)

    async def initialize(self) -> None:
        pass


class NoneComponent(BaseComponent):
    """The component that does nothing, just acts as a placeholder."""

    def __init__(self):
        super().__init__()

    async def initialize(self) -> None:
        pass
