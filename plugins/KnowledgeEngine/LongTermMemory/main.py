from __future__ import annotations

import logging

from langbot_plugin.api.definition.plugin import BasePlugin

from store.memory_store import MemoryStore

logger = logging.getLogger(__name__)


class LongTermMemoryPlugin(BasePlugin):

    memory_store: MemoryStore

    async def initialize(self) -> None:
        # Initialization is process-scoped; config is resolved at invocation time.
        self.memory_store = MemoryStore(plugin=self)
        logger.info("[LongTermMemory] plugin initialized")

    async def on_installation_revoked(self, binding) -> None:
        """Release process-local state keyed by one revoked installation.

        One object graph serves every installation of the artifact (shared by
        digest, never destroyed per installation), so a revoked installation's
        locks and fence cache are only released here. The hook runs without an
        invocation context, so it may only touch process-local state; needs an
        SDK whose runtime dispatches it (langbot-plugin 0.7.4 never does).
        """
        store = getattr(self, 'memory_store', None)
        release = getattr(store, 'release_binding', None)
        if release is not None:
            release(binding)
