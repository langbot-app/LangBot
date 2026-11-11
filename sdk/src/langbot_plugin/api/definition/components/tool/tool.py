from __future__ import annotations

import abc
from typing import Any

from langbot_plugin.api.definition.components.base import BaseComponent
from langbot_plugin.api.entities.builtin.provider import session as provider_session


class Tool(BaseComponent):
    """The tool component."""

    __kind__ = "Tool"

    @abc.abstractmethod
    async def call(
        self, params: dict[str, Any], session: provider_session.Session, query_id: int
    ) -> str:
        """Call the tool."""
        pass
