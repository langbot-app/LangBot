from __future__ import annotations

from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy


class ExecuteContextProxy(QueryBasedAPIProxy, ExecuteContext):
    """The proxy for execute context."""
