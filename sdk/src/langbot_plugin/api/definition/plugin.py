from __future__ import annotations

import abc
import typing

from langbot_plugin.api.proxies import langbot_api
from langbot_plugin.api.proxies.invocation import current_binding, current_config

if typing.TYPE_CHECKING:
    from langbot_plugin.entities.io.context import InstallationBinding


class BasePlugin(abc.ABC, langbot_api.LangBotAPIProxy):
    """The base class for all plugins."""

    _legacy_config: dict[str, typing.Any]

    @property
    def config(self) -> dict[str, typing.Any]:
        """Expose task-local config while preserving dedicated plugin behavior."""

        scoped = current_config(getattr(self, "plugin_runtime_handler", None))
        if scoped is not None:
            return dict(scoped)
        return getattr(self, "_legacy_config", {})

    @config.setter
    def config(self, value: dict[str, typing.Any] | None) -> None:
        # Legacy plugins initialize this attribute to None before runtime binding.
        self._legacy_config = {} if value is None else dict(value)

    def get_config(self) -> dict[str, typing.Any]:
        """Return the active invocation config, or the legacy dedicated config."""

        return self.config

    def get_installation_binding(self):
        """Return the active certified installation binding, if any."""

        return current_binding(getattr(self, "plugin_runtime_handler", None))

    def __init__(self):
        self._legacy_config = {}

    async def initialize(self) -> None:
        pass

    async def on_installation_revoked(self, binding: InstallationBinding) -> None:
        """Release process-local state held for one revoked installation.

        The runtime calls this once per installation, after that installation's
        in-flight messages have been cancelled and its slot detached, and before
        anything else may reuse the object graph. Shared placement calls it for
        uninstall, disable, workspace removal and upgrade (the superseded binding
        is revoked when the new revision activates). Dedicated workers are shut
        down instead of detached, so their process-local state disappears with
        the process and this hook is not called.

        Shared-runtime plugins must drop every cache or registry entry keyed by
        this binding here: one object graph serves every installation of the
        artifact digest and is never destroyed per installation.

        There is no active invocation, so Host APIs (storage, config, binding
        lookups) are unavailable. Only process-local state can be touched, and
        only the given `binding` identifies the installation. Return `None`;
        exceptions are logged and never block revocation. The call is serialized
        per installation but may overlap with invocations of sibling
        installations on the same object graph.
        """

        return None

    def __del__(self) -> None:
        pass


class NonePlugin(BasePlugin):
    """The plugin that does nothing, just acts as a placeholder."""

    def __init__(self):
        super().__init__()
