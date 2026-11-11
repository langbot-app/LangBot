from __future__ import annotations

from langbot_plugin.api.entities.context import EventContext
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy


class EventContextProxy(QueryBasedAPIProxy, EventContext):
    """The proxy for event context."""
