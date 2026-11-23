"""Neutral MCP server configuration helpers for Runner integrations."""

from __future__ import annotations

import dataclasses
import typing
import urllib.parse


@dataclasses.dataclass(frozen=True)
class AgentMCPServerConfig:
    """Neutral MCP server config used by runner plugins.

    Runner integrations can adapt this model to ACP, Claude Code, Codex, or any
    other runtime-specific MCP config shape without depending on SDK internals.
    """

    name: str
    transport: str
    url: str = ""
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    command: str = ""
    args: tuple[str, ...] = ()
    env: dict[str, str] = dataclasses.field(default_factory=dict)

    @classmethod
    def stdio(
        cls,
        *,
        name: str,
        command: str,
        args: typing.Sequence[str] = (),
        env: dict[str, str] | None = None,
    ) -> "AgentMCPServerConfig":
        return cls(
            name=name,
            transport="stdio",
            command=command,
            args=tuple(str(item) for item in args),
            env={str(key): str(value) for key, value in dict(env or {}).items()},
        )

    @classmethod
    def http(
        cls,
        *,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        transport: str = "http",
    ) -> "AgentMCPServerConfig":
        return cls(
            name=name,
            transport=transport,
            url=url,
            headers={
                str(key): str(value) for key, value in dict(headers or {}).items()
            },
        )

    @classmethod
    def from_dict(cls, data: dict[str, typing.Any]) -> "AgentMCPServerConfig":
        transport = str(data.get("transport") or data.get("type") or "").strip()
        if not transport:
            transport = "http" if data.get("url") else "stdio"
        return cls(
            name=str(data.get("name") or ""),
            transport=transport,
            url=str(data.get("url") or ""),
            headers={
                str(k): str(v) for k, v in dict(data.get("headers") or {}).items()
            },
            command=str(data.get("command") or ""),
            args=tuple(str(item) for item in data.get("args") or ()),
            env={str(k): str(v) for k, v in dict(data.get("env") or {}).items()},
        )

    def to_dict(self, *, include_type: bool = False) -> dict[str, typing.Any]:
        data: dict[str, typing.Any] = {
            "name": self.name,
            "transport": self.transport,
        }
        if include_type:
            data["type"] = self.transport
        if self.url:
            data["url"] = self.url
        if self.headers:
            data["headers"] = dict(self.headers)
        if self.command:
            data["command"] = self.command
        if self.args:
            data["args"] = list(self.args)
        if self.env:
            data["env"] = dict(self.env)
        return data


@dataclasses.dataclass(frozen=True)
class AgentMCPReverseTunnel:
    """SSH reverse tunnel that exposes a local MCP endpoint on a remote host."""

    remote_host: str
    remote_port: int
    local_host: str
    local_port: int

    @property
    def spec(self) -> str:
        return (
            f"{self.remote_host}:{self.remote_port}:{self.local_host}:{self.local_port}"
        )

    def ssh_args(self) -> list[str]:
        return ["-R", self.spec]


def reverse_tunnel_for_endpoint(
    endpoint: str,
    *,
    remote_host: str = "127.0.0.1",
    local_host: str = "127.0.0.1",
) -> AgentMCPReverseTunnel:
    """Create an SSH reverse tunnel for an HTTP MCP endpoint."""

    parsed = urllib.parse.urlparse(str(endpoint))
    if not parsed.port:
        raise ValueError("MCP endpoint did not include a port")
    return AgentMCPReverseTunnel(
        remote_host=remote_host,
        remote_port=parsed.port,
        local_host=local_host,
        local_port=parsed.port,
    )


def reverse_tunnel_for_mcp_server(
    server: AgentMCPServerConfig,
    *,
    remote_host: str = "127.0.0.1",
    local_host: str = "127.0.0.1",
) -> AgentMCPReverseTunnel:
    if not server.url:
        raise ValueError("MCP server config did not include a URL")
    return reverse_tunnel_for_endpoint(
        server.url,
        remote_host=remote_host,
        local_host=local_host,
    )
