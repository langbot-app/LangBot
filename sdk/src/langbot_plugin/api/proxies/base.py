from __future__ import annotations

import abc

from langbot_plugin.cli.run.handler import PluginRuntimeHandler
from langbot_plugin.runtime.plugin.container import PluginContainer


class APIProxy(abc.ABC):
    """The base class for all API proxies."""

    plugin_runtime_handler: PluginRuntimeHandler
    plugin_container: PluginContainer

    def __init__(
        self,
        plugin_runtime_handler: PluginRuntimeHandler,
        plugin_container: PluginContainer,
    ):
        self.plugin_runtime_handler = plugin_runtime_handler
        self.plugin_container = plugin_container
