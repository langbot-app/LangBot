"""Public run-scoped RunnerAPIProxy implementation."""

from __future__ import annotations

from langbot_plugin.api.proxies.runner.box import RunnerBoxAPIMixin

from langbot_plugin.api.proxies.runner.common import AgentRunProxyBase
from langbot_plugin.api.proxies.runner.context import RunnerContextAPIMixin
from langbot_plugin.api.proxies.runner.ledger import AgentRunLedgerAPIMixin
from langbot_plugin.api.proxies.runner.resources import AgentRunResourceAPIMixin
from langbot_plugin.api.proxies.runner.reply_stream import (
    AgentRunReplyStreamAPIMixin,
)
from langbot_plugin.api.proxies.runner.state import AgentRunStateAPIMixin


from langbot_plugin.api.proxies.runner.platform import RunnerPlatformAPIMixin


class RunnerAPIProxy(
    RunnerBoxAPIMixin,
    RunnerPlatformAPIMixin,
    AgentRunReplyStreamAPIMixin,
    AgentRunResourceAPIMixin,
    RunnerContextAPIMixin,
    AgentRunLedgerAPIMixin,
    AgentRunStateAPIMixin,
    AgentRunProxyBase,
):
    """Restricted API proxy for Runner execution.

    The public surface stays on one object for plugin ergonomics, while the
    implementation is split by host capability boundary: resources, context
    pull, run ledger, and state.
    """

    pass
