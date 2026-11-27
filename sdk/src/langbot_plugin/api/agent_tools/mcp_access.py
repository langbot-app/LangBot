"""Run-scoped MCP access helper for external Runner runtimes."""

from __future__ import annotations

import typing

from langbot_plugin.api.agent_tools.asset_gateway import (
    AgentAssetGatewayRegistration,
    get_default_agent_asset_gateway,
)
from langbot_plugin.api.agent_tools.mcp_bridge import AgentRunMCPBridge
from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_config import (
    AgentMCPReverseTunnel,
    AgentMCPServerConfig,
    reverse_tunnel_for_mcp_server,
)
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.runner import RunnerAPIProxy


class AgentRunMCPAccess:
    """Owns a run-scoped LangBot MCP bridge or gateway registration."""

    def __init__(
        self,
        api: RunnerAPIProxy,
        ctx: RunnerContext,
        *,
        enabled: bool = True,
        location: str = "local",
        mode: str = "auto",
        transport: str = "auto",
        bridge_host: str = "127.0.0.1",
        bridge_port: int = 0,
        bridge_public_url: str = "",
        bridge_request_timeout: float = 60.0,
        gateway_host: str = "127.0.0.1",
        gateway_port: int = 0,
        gateway_public_url: str = "",
        gateway_request_timeout: float = 60.0,
        gateway_token_ttl: float = 3600.0,
        tools: AgentRunExternalTools | None = None,
    ) -> None:
        self.api = api
        self.ctx = ctx
        self.enabled = enabled
        self.location = location
        self.mode = "ephemeral" if mode == "auto" else mode
        self.transport = transport
        self.bridge_host = bridge_host
        self.bridge_port = bridge_port
        self.bridge_public_url = bridge_public_url
        self.bridge_request_timeout = bridge_request_timeout
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self.gateway_public_url = gateway_public_url
        self.gateway_request_timeout = gateway_request_timeout
        self.gateway_token_ttl = gateway_token_ttl
        self.tools = tools
        self._handle: AgentRunMCPBridge | AgentAssetGatewayRegistration | None = None
        self._server_config: AgentMCPServerConfig | None = None
        self._reverse_tunnel: AgentMCPReverseTunnel | None = None

    @property
    def handle(self) -> AgentRunMCPBridge | AgentAssetGatewayRegistration | None:
        return self._handle

    @property
    def server_config(self) -> AgentMCPServerConfig | None:
        return self._server_config

    @property
    def reverse_tunnel(self) -> AgentMCPReverseTunnel | None:
        return self._reverse_tunnel

    def start(self) -> None:
        if not self.enabled or self._server_config is not None:
            return

        if self.mode == "gateway":
            if self.tools is not None:
                raise ValueError(
                    "Custom Runner tools require ephemeral MCP access mode"
                )
            gateway = get_default_agent_asset_gateway(
                host=self.gateway_host,
                port=self.gateway_port,
                request_timeout=self.gateway_request_timeout,
            )
            registration = gateway.register_run(
                self.api,
                self.ctx,
                ttl_seconds=self.gateway_token_ttl,
            )
            external_public_url = self.gateway_public_url
            public_url = external_public_url
            if not public_url and self.location == "remote-ssh":
                public_url = registration.http_mcp_endpoint
            self._handle = registration
            self._server_config = registration.mcp_server(
                public_url=public_url or None,
            )
            self._reverse_tunnel = self._remote_reverse_tunnel(external_public_url)
            return

        bridge = (
            AgentRunMCPBridge(
                self.tools,
                host=self.bridge_host,
                port=self.bridge_port,
                request_timeout=self.bridge_request_timeout,
            )
            if self.tools is not None
            else AgentRunMCPBridge.from_run_api(
                self.api,
                self.ctx,
                host=self.bridge_host,
                port=self.bridge_port,
                request_timeout=self.bridge_request_timeout,
            )
        )
        bridge.start()

        transport = self.transport
        if transport == "auto":
            transport = "http" if self.location == "remote-ssh" else "stdio"
        if transport not in {"stdio", "http"}:
            raise ValueError("MCP transport must be auto, stdio, or http")

        external_public_url = self.bridge_public_url
        public_url = external_public_url
        if not public_url and self.location == "remote-ssh" and transport == "http":
            public_url = bridge.http_mcp_endpoint
        self._handle = bridge
        self._server_config = bridge.mcp_server(
            transport=transport,
            public_url=public_url or None,
        )
        self._reverse_tunnel = self._remote_reverse_tunnel(external_public_url)

    def stop(self) -> None:
        handle = self._handle
        self._handle = None
        self._server_config = None
        self._reverse_tunnel = None
        if handle is not None:
            handle.stop()

    def _remote_reverse_tunnel(self, public_url: str) -> AgentMCPReverseTunnel | None:
        if self.location != "remote-ssh" or public_url:
            return None
        if self._server_config is None or self._server_config.transport != "http":
            return None
        return reverse_tunnel_for_mcp_server(self._server_config)

    def __enter__(self) -> "AgentRunMCPAccess":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: typing.Any,
    ) -> None:
        self.stop()
