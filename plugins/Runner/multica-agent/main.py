"""Multica Agent plugin entry point."""

from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin
from pkg.i18n import DEFAULT_LANGUAGE, normalize_language


class MulticaAgentPlugin(BasePlugin):
    """Multica Agent plugin."""

    def __init__(self):
        super().__init__()

    async def initialize(self) -> None:
        """Initialize the plugin."""
        pass

    def get_language(self) -> str:
        """Language configured for the current invocation.

        Read on every call, never cached in initialize(): in the shared runtime one
        object graph serves every installation, so installation config is only
        resolvable per invocation.
        """
        return normalize_language(self.get_config().get("language") or DEFAULT_LANGUAGE)
