"""ACP default Runner implementation."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shlex
import time
import typing

from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_access import AgentRunMCPAccess
from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    AgentInput,
    RunnerContext,
    RunnerResult,
)
from pkg.acp_client import AcpError, AcpStdioClient
from pkg.daemon_relay import (
    AgentRuntimeDaemonError,
    agent_runtime_daemon_config_from_plugin_config,
    get_agent_runtime_daemon_hub,
)
from pkg.prompt import acp_prompt_blocks, has_acp_prompt_input, prompt_capabilities
from pkg.runtime_support import local_workspace
from pkg.session import CLAUDE_ENV_VARS_TO_UNSET, build_session_params
from pkg.steering import run_with_steering

logger = logging.getLogger(__name__)

ACP_SESSION_STATE_KEY = "external.acp_session_id"
# Common ACP agent launch presets from the public ACP registry and vendor docs.
# Pin adapters when runner behavior depends on a specific ACP lifecycle fix;
# set acp-command to use a different tested version or install path.
DEFAULT_PROVIDER_COMMANDS = {
    "auggie": "npx -y @augmentcode/auggie --acp",
    "autohand": "npx -y @autohandai/autohand-acp",
    "claude-code": "npx -y @agentclientprotocol/claude-agent-acp@0.62.0",
    "codebuddy-code": "npx -y @tencent-ai/codebuddy-code --acp",
    "codex": "npx -y @zed-industries/codex-acp",
    "deepagents": "npx -y deepagents-acp",
    "dimcode": "npx -y dimcode acp",
    "dirac": "npx -y dirac-cli --acp",
    "factory-droid": "npx -y droid exec --output-format acp-daemon",
    "gemini": "npx -y @google/gemini-cli --acp",
    "glm-agent": "npx -y glm-acp-agent",
    "kilo": "npx -y @kilocode/cli acp",
    "opencode": "opencode acp",
    "pi-acp": "npx -y pi-acp",
    "qwen-code": "npx -y @qwen-code/qwen-code --acp --experimental-skills",
}
SUPPORTED_PROVIDERS = set(DEFAULT_PROVIDER_COMMANDS) | {"custom"}
SUPPORTED_LOCATIONS = {"local", "remote-ssh", "daemon"}
SUPPORTED_REMOTE_SHELLS = {"bash", "powershell", "none"}
SUPPORTED_LANGBOT_ASSET_MODES = {"auto", "ephemeral", "gateway"}
ACP_COMMAND_CONFIG_KEYS = ("acp-command", "remote-command", "local-command")
WORKSPACE_CONFIG_KEYS = ("workspace",)
REMOTE_WORKSPACE_CONFIG_KEYS = ("remote-workspace", "session-cwd")
LOCAL_WORKSPACE_CONFIG_KEYS = ("local-workspace", "cwd", "session-cwd")
SSH_TARGET_CONFIG_KEYS = ("ssh-target", "ssh_target")
DAEMON_ID_CONFIG_KEYS = ("daemon-id", "daemon_id")
SSH_IDENTITY_FILE_CONFIG_KEYS = ("ssh-identity-file", "ssh-key-file")
ASSET_GATEWAY_PUBLIC_URL_CONFIG_KEYS = ("langbot-assets-gateway-public-url", "mcp-public-url")


def _to_bool(value: typing.Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _to_float(value: typing.Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: typing.Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_args(value: typing.Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return shlex.split(text)


def _parse_json_object(value: typing.Any, *, label: str) -> dict[str, typing.Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise AcpError(f"{label} must be a JSON object: {exc}", code="acp.config_invalid") from exc
    if not isinstance(parsed, dict):
        raise AcpError(f"{label} must be a JSON object", code="acp.config_invalid")
    return parsed


def _parse_json_list(value: typing.Any, *, label: str) -> list[typing.Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise AcpError(f"{label} must be a JSON array: {exc}", code="acp.config_invalid") from exc
    if not isinstance(parsed, list):
        raise AcpError(f"{label} must be a JSON array", code="acp.config_invalid")
    return parsed


def _first_config_value(config: dict[str, typing.Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = config.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _shell_command(command: str, command_args: typing.Sequence[str]) -> str:
    parts = (command, *command_args)
    return " ".join(shlex.quote(part) for part in parts if part)


def _posix_quote(value: str) -> str:
    return shlex.quote(str(value))


def _powershell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _remote_shell_command(
    *,
    remote_shell: str,
    workspace: str,
    acp_command: str,
    env: dict[str, str] | None = None,
    unset_env: typing.Sequence[str] = (),
) -> str:
    remote_env = dict(env or {})
    if remote_shell == "none":
        unset_prefix = " ".join(f"-u {_posix_quote(name)}" for name in unset_env)
        env_prefix = " ".join(f"{_posix_quote(name)}={_posix_quote(value)}" for name, value in remote_env.items())
        prefixes = " ".join(part for part in (unset_prefix, env_prefix) if part)
        return f"env {prefixes} {acp_command}" if prefixes else acp_command

    if remote_shell == "powershell":
        script_parts = ["$ErrorActionPreference='Stop'"]
        script_parts.extend(f"Remove-Item Env:{name} -ErrorAction SilentlyContinue" for name in unset_env)
        script_parts.extend(
            f"Set-Item -Path {_powershell_quote(f'Env:{name}')} -Value {_powershell_quote(value)}"
            for name, value in remote_env.items()
            if name not in unset_env
        )
        if workspace:
            quoted_workspace = _powershell_quote(workspace)
            script_parts.append(f"New-Item -ItemType Directory -Force -Path {quoted_workspace} | Out-Null")
            script_parts.append(f"Set-Location -LiteralPath {quoted_workspace}")
        script_parts.append(acp_command)
        return f"powershell -NoProfile -ExecutionPolicy Bypass -Command {_posix_quote('; '.join(script_parts))}"

    script_parts = []
    script_parts.extend(
        f"export {_posix_quote(name)}={_posix_quote(value)}"
        for name, value in remote_env.items()
        if name not in unset_env
    )
    if workspace:
        quoted_workspace = _posix_quote(workspace)
        script_parts.append(f"mkdir -p {quoted_workspace}")
        script_parts.append(f"cd {quoted_workspace}")
    unset_prefix = " ".join(f"-u {_posix_quote(name)}" for name in unset_env)
    command = f"env {unset_prefix} {acp_command}" if unset_prefix else acp_command
    script_parts.append(f"exec {command}")
    return f"bash -lc {_posix_quote(' && '.join(script_parts))}"


def _mcp_bridge_tool_names(ctx: RunnerContext) -> list[str]:
    tool_names = ["langbot_get_current_event", "langbot_list_assets"]
    if ctx.context.available_apis.history_page:
        tool_names.append("langbot_history_page")
    if ctx.resources.knowledge_bases:
        tool_names.append("langbot_retrieve_knowledge")
    if ctx.resources.tools:
        tool_names.append("langbot_get_tool_detail")
        tool_names.append("langbot_call_tool")
    return tool_names


def _resource_summary(ctx: RunnerContext) -> dict[str, typing.Any]:
    ordinary_tools = [item for item in ctx.resources.tools if item.tool_type != "platform"]
    platform_tools = [item for item in ctx.resources.tools if item.tool_type == "platform"]
    return {
        "knowledge_bases": [
            {
                "kb_id": item.kb_id,
                "name": item.kb_name,
                "type": item.kb_type,
            }
            for item in ctx.resources.knowledge_bases
        ],
        "tools": [
            {
                "tool_name": item.tool_name,
                "type": item.tool_type,
                "description": item.description,
            }
            for item in ordinary_tools
        ],
        "platform_tools": [
            {
                "tool_name": item.tool_name,
                "description": item.description,
            }
            for item in platform_tools
        ],
        "mcp_bridge_tools": [{"tool_name": name} for name in _mcp_bridge_tool_names(ctx)],
    }


def _extract_session_id(result: typing.Any) -> str:
    if not isinstance(result, dict):
        return ""
    session_id = result.get("sessionId") or result.get("session_id") or result.get("id")
    return str(session_id or "").strip()


def _runtime_has_method(capabilities: dict[str, typing.Any], method: str) -> bool:
    if method == "session/load":
        return bool(capabilities.get("loadSession"))
    if method.startswith("session/"):
        session_capabilities = capabilities.get("sessionCapabilities")
        if isinstance(session_capabilities, dict):
            capability_key = method.split("/", 1)[1].replace("-", "_")
            for key in (capability_key, method.split("/", 1)[1]):
                if key in session_capabilities:
                    value = session_capabilities[key]
                    return value is not None and value is not False
    methods = capabilities.get("methods")
    if isinstance(methods, list) and method in {str(item) for item in methods}:
        return True
    key = method.replace("/", "_").replace("-", "_")
    value = capabilities.get(method) or capabilities.get(key)
    return bool(value)


def _content_text(value: typing.Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    if value.get("type") == "text" and isinstance(value.get("text"), str):
        return str(value["text"])
    text = value.get("text")
    if isinstance(text, str):
        return text
    return ""


def _agent_text_from_update(update: dict[str, typing.Any]) -> str:
    payload = update.get("update") if isinstance(update.get("update"), dict) else update
    if not isinstance(payload, dict):
        return ""

    update_kind = str(payload.get("sessionUpdate") or payload.get("kind") or payload.get("type") or "")
    content = payload.get("content")

    if update_kind == "agent_message_chunk":
        return _content_text(content)

    if "agent_message" in update_kind or payload.get("role") == "assistant":
        if isinstance(content, list):
            return "".join(_content_text(item) for item in content)
        return _content_text(content)

    return ""


def _agent_message_id(update: dict[str, typing.Any]) -> str:
    payload = update.get("update") if isinstance(update.get("update"), dict) else update
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("messageId") or payload.get("message_id") or "")


def _tool_update_payload(update: dict[str, typing.Any]) -> dict[str, typing.Any] | None:
    payload = update.get("update") if isinstance(update.get("update"), dict) else update
    if not isinstance(payload, dict):
        return None
    update_kind = str(payload.get("sessionUpdate") or payload.get("kind") or payload.get("type") or "")
    if "tool_call" not in update_kind:
        return None
    return payload


def _tool_update_name(payload: dict[str, typing.Any]) -> str:
    metadata = payload.get("_meta")
    if isinstance(metadata, dict):
        for value in metadata.values():
            if isinstance(value, dict) and value.get("toolName"):
                return str(value["toolName"])
    return str(payload.get("name") or payload.get("title") or "acp_tool")


def _mcp_env_to_acp(env: typing.Any) -> list[dict[str, str]]:
    if isinstance(env, dict):
        return [{"name": str(key), "value": str(value)} for key, value in env.items()]
    if isinstance(env, list):
        converted = []
        for item in env:
            if isinstance(item, dict) and "name" in item and "value" in item:
                converted.append({"name": str(item["name"]), "value": str(item["value"])})
        return converted
    return []


def _mcp_headers_to_acp(headers: typing.Any) -> list[dict[str, str]]:
    if isinstance(headers, dict):
        return [{"name": str(key), "value": str(value)} for key, value in headers.items()]
    if isinstance(headers, list):
        converted = []
        for item in headers:
            if isinstance(item, dict) and "name" in item and "value" in item:
                converted.append({"name": str(item["name"]), "value": str(item["value"])})
        return converted
    return []


class DefaultRunner(Runner):
    """Runner for Agent Client Protocol compatible agents."""

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        config = ctx.config or {}
        provider = str(config.get("provider", "claude-code") or "claude-code").strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise AcpError(
                f"provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
                code="acp.config_invalid",
            )

        location = str(config.get("location", "local") or "local").strip()
        if location not in SUPPORTED_LOCATIONS:
            raise AcpError(
                f"location must be one of: {', '.join(sorted(SUPPORTED_LOCATIONS))}",
                code="acp.config_invalid",
            )

        command = str(config.get("command", "") or "").strip()
        command_args = _parse_args(config.get("args"))
        acp_command = _first_config_value(config, ACP_COMMAND_CONFIG_KEYS)
        if not acp_command and command:
            acp_command = _shell_command(command, command_args)
        if not acp_command:
            acp_command = DEFAULT_PROVIDER_COMMANDS.get(provider, "")
        if not acp_command:
            raise AcpError("acp-command is required when provider=custom", code="acp.config_invalid")

        workspace = _first_config_value(config, WORKSPACE_CONFIG_KEYS)
        if not workspace:
            if location == "remote-ssh":
                workspace = _first_config_value(config, REMOTE_WORKSPACE_CONFIG_KEYS)
            else:
                workspace = _first_config_value(config, LOCAL_WORKSPACE_CONFIG_KEYS) or os.getcwd()
        if location == "remote-ssh" and not workspace:
            raise AcpError("workspace is required when location=remote-ssh", code="acp.config_invalid")

        if location == "local":
            workspace = local_workspace(
                _first_config_value(config, WORKSPACE_CONFIG_KEYS)
                or _first_config_value(config, LOCAL_WORKSPACE_CONFIG_KEYS)
            )

        ssh_target = _first_config_value(config, SSH_TARGET_CONFIG_KEYS)
        if location == "remote-ssh" and not ssh_target:
            raise AcpError("ssh-target is required when location=remote-ssh", code="acp.config_invalid")

        daemon_id = _first_config_value(config, DAEMON_ID_CONFIG_KEYS)
        if location == "daemon" and not daemon_id:
            raise AcpError("daemon-id is required when location=daemon", code="acp.config_invalid")
        # The daemon hub is a process-wide socket keyed by daemon ID. Until it
        # can bind clients and jobs to a full installation capability, accepting
        # daemon runs in a shared Worker would grant another tenant access.
        if location == "daemon" and os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            raise AcpError("daemon mode is unavailable in shared runtime", code="acp.config_invalid")

        remote_shell = str(config.get("remote-shell", "bash") or "bash").strip()
        if remote_shell not in SUPPORTED_REMOTE_SHELLS:
            raise AcpError(
                f"remote-shell must be one of: {', '.join(sorted(SUPPORTED_REMOTE_SHELLS))}",
                code="acp.config_invalid",
            )

        permission_decision = str(config.get("permission-decision", "allow_once") or "allow_once").strip()
        if permission_decision not in {"allow_once", "reject_once", "first"}:
            raise AcpError(
                "permission-decision must be allow_once, reject_once, or first",
                code="acp.config_invalid",
            )

        langbot_assets_mode = str(config.get("langbot-assets-mode", "auto") or "auto").strip()
        if langbot_assets_mode not in SUPPORTED_LANGBOT_ASSET_MODES:
            raise AcpError(
                "langbot-assets-mode must be auto, ephemeral, or gateway",
                code="acp.config_invalid",
            )

        return {
            "provider": provider,
            "location": location,
            "acp_command": acp_command,
            "workspace": workspace,
            "cwd": workspace if location == "local" else None,
            "session_cwd": workspace,
            "env": {str(k): str(v) for k, v in _parse_json_object(config.get("env-json"), label="env-json").items()},
            "ssh_target": ssh_target,
            "ssh_port": _to_int(config.get("ssh-port"), 22),
            "ssh_identity_file": _first_config_value(config, SSH_IDENTITY_FILE_CONFIG_KEYS),
            "ssh_connect_timeout": _to_int(config.get("ssh-connect-timeout"), 10),
            "ssh_extra_options": _parse_args(config.get("ssh-extra-options")),
            "daemon_id": daemon_id,
            "daemon_connect_timeout": _to_float(config.get("daemon-connect-timeout"), 30.0),
            "remote_shell": remote_shell,
            "timeout": _to_float(config.get("timeout"), 300.0),
            "startup_timeout": _to_float(config.get("startup-timeout"), 30.0),
            "initialize_timeout": _to_float(config.get("initialize-timeout"), 30.0),
            "reuse_session": _to_bool(config.get("reuse-session"), True),
            "create_session_if_missing": _to_bool(config.get("create-session-if-missing"), True),
            "streaming": _to_bool(config.get("streaming"), True),
            "permission_decision": permission_decision,
            "append_run_scope_prompt": _to_bool(config.get("append-run-scope-prompt"), True),
            "mcp_bridge_enabled": _to_bool(
                config.get("langbot-assets-enabled", config.get("mcp-bridge-enabled")),
                True,
            ),
            "mcp_bridge_host": str(config.get("mcp-bridge-host", "127.0.0.1") or "127.0.0.1").strip(),
            "mcp_bridge_port": _to_int(config.get("mcp-bridge-port"), 0),
            "mcp_bridge_request_timeout": _to_float(config.get("mcp-bridge-request-timeout"), 60.0),
            "mcp_bridge_transport": str(config.get("mcp-bridge-transport", "auto") or "auto").strip(),
            "mcp_public_url": str(config.get("mcp-public-url", "") or "").strip(),
            "mcp_servers": _parse_json_list(config.get("mcp-servers-json"), label="mcp-servers-json"),
            "langbot_assets_mode": langbot_assets_mode,
            "asset_gateway_host": str(
                config.get("langbot-assets-gateway-host", config.get("mcp-bridge-host", "127.0.0.1")) or "127.0.0.1"
            ).strip(),
            "asset_gateway_port": _to_int(
                config.get("langbot-assets-gateway-port", config.get("mcp-bridge-port")),
                0,
            ),
            "asset_gateway_request_timeout": _to_float(
                config.get("langbot-assets-gateway-request-timeout", config.get("mcp-bridge-request-timeout")),
                60.0,
            ),
            "asset_gateway_token_ttl": _to_float(config.get("langbot-assets-token-ttl"), 3600.0),
            "asset_gateway_public_url": _first_config_value(config, ASSET_GATEWAY_PUBLIC_URL_CONFIG_KEYS),
            "daemon_hub": agent_runtime_daemon_config_from_plugin_config(
                self.get_plugin_config(),
                env_prefix="LANGBOT_ACP_DAEMON",
            ),
        }

    def _input_text(self, ctx: RunnerContext) -> str:
        return ctx.input.to_text()

    def _with_run_scope_prompt(self, ctx: RunnerContext, input_text: str) -> str:
        resources = json.dumps(_resource_summary(ctx), ensure_ascii=True, separators=(",", ":"))
        return (
            "System instructions from LangBot:\n"
            f"- Current LangBot run_id: {ctx.run_id}\n"
            "- The injected LangBot MCP server is already scoped to this run. Follow its tool schemas exactly.\n"
            "- Call LangBot MCP tools directly in this ACP session when possible.\n"
            "- Do not launch background agents, workflows, or tasks. If this model can only call MCP tools through an Agent, "
            "launch at most one Agent with run_in_background=false and wait for it to finish.\n"
            "- Wait for each LangBot MCP tool result before replying to the user.\n"
            "- Do not add run_id or other fields to MCP tool calls unless the tool schema asks for them.\n"
            "- If a LangBot MCP call is rejected, stop and report the error.\n"
            f"- Authorized LangBot resources and MCP bridge tools for this run: {resources}\n\n"
            "User input:\n"
            f"{input_text}"
        )

    def _stored_session_id(self, ctx: RunnerContext) -> str:
        return str(ctx.state.conversation.get(ACP_SESSION_STATE_KEY) or "").strip()

    def _mcp_server_to_acp(self, server: AgentMCPServerConfig) -> dict[str, typing.Any]:
        if server.transport == "http":
            return {
                "name": server.name,
                "type": "http",
                "url": server.url,
                "headers": _mcp_headers_to_acp(server.headers),
            }
        if server.transport != "stdio":
            raise AcpError(f"unsupported MCP transport: {server.transport}", code="acp.mcp_bridge_invalid")
        return {
            "name": server.name,
            "type": "stdio",
            "command": server.command,
            "args": list(server.args),
            "env": _mcp_env_to_acp(server.env),
        }

    def _mcp_servers(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
    ) -> tuple[AgentRunMCPAccess | None, list[dict[str, typing.Any]]]:
        servers = [server for server in config["mcp_servers"] if isinstance(server, dict)]
        if not config["mcp_bridge_enabled"]:
            return None, servers

        if config["mcp_bridge_transport"] not in {"auto", "stdio", "http"}:
            raise AcpError("mcp-bridge-transport must be auto, stdio, or http", code="acp.config_invalid")

        access = AgentRunMCPAccess(
            self.get_run_api(ctx),
            ctx,
            enabled=True,
            location=config["location"],
            mode=config["langbot_assets_mode"],
            transport=config["mcp_bridge_transport"],
            bridge_host=config["mcp_bridge_host"],
            bridge_port=config["mcp_bridge_port"],
            bridge_public_url=config["mcp_public_url"],
            bridge_request_timeout=config["mcp_bridge_request_timeout"],
            gateway_host=config["asset_gateway_host"],
            gateway_port=config["asset_gateway_port"],
            gateway_public_url=config["asset_gateway_public_url"],
            gateway_request_timeout=config["asset_gateway_request_timeout"],
            gateway_token_ttl=config["asset_gateway_token_ttl"],
        )
        access.start()
        if access.server_config is not None:
            servers.append(self._mcp_server_to_acp(access.server_config))
        return access, servers

    def _launch_config(self, config: dict[str, typing.Any], access: AgentRunMCPAccess | None) -> dict[str, typing.Any]:
        unset_env = CLAUDE_ENV_VARS_TO_UNSET if config["provider"] == "claude-code" else ()
        if config["location"] == "local":
            argv = _parse_args(config["acp_command"])
            if not argv:
                raise AcpError("acp-command is required", code="acp.config_invalid")
            return {
                "command": argv[0],
                "args": argv[1:],
                "cwd": config["cwd"],
                "unset_env": unset_env,
            }

        ssh_args = [
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            f"ConnectTimeout={config['ssh_connect_timeout']}",
            "-p",
            str(config["ssh_port"]),
        ]
        if config["ssh_identity_file"]:
            ssh_args.extend(["-i", config["ssh_identity_file"]])
        ssh_args.extend(config["ssh_extra_options"])

        if access is not None and access.reverse_tunnel is not None:
            ssh_args.extend(access.reverse_tunnel.ssh_args())

        ssh_args.append(config["ssh_target"])
        ssh_args.append(
            _remote_shell_command(
                remote_shell=config["remote_shell"],
                workspace=config["workspace"],
                acp_command=config["acp_command"],
                env=config["env"],
                unset_env=unset_env,
            )
        )
        return {
            "command": "ssh",
            "args": ssh_args,
            "cwd": None,
            "unset_env": unset_env,
        }

    async def _create_or_resume_session(
        self,
        client: AcpStdioClient,
        initialize_result: dict[str, typing.Any],
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        mcp_servers: list[dict[str, typing.Any]],
        stored_session_id: str,
    ) -> tuple[str, bool]:
        capabilities = initialize_result.get("agentCapabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}

        if stored_session_id and config["reuse_session"]:
            if _runtime_has_method(capabilities, "session/resume"):
                result = await client.request(
                    "session/resume",
                    build_session_params(
                        provider=config["provider"],
                        session_id=stored_session_id,
                        cwd=config["session_cwd"],
                        mcp_servers=mcp_servers,
                    ),
                    timeout=config["timeout"],
                )
                return _extract_session_id(result) or stored_session_id, False
            if _runtime_has_method(capabilities, "session/load"):
                result = await client.request(
                    "session/load",
                    build_session_params(
                        provider=config["provider"],
                        session_id=stored_session_id,
                        cwd=config["session_cwd"],
                        mcp_servers=mcp_servers,
                    ),
                    timeout=config["timeout"],
                )
                await client.drain_updates()
                return _extract_session_id(result) or stored_session_id, False

        if not config["create_session_if_missing"]:
            raise AcpError(
                "no stored ACP session and create-session-if-missing is disabled", code="acp.session_missing"
            )

        result = await client.request(
            "session/new",
            build_session_params(
                provider=config["provider"],
                cwd=config["session_cwd"],
                mcp_servers=mcp_servers,
            ),
            timeout=config["timeout"],
        )
        session_id = _extract_session_id(result)
        if not session_id:
            raise AcpError(f"ACP session/new did not return a session id: {result!r}", code="acp.response_invalid")
        return session_id, True

    async def _stream_prompt_results(
        self,
        client: AcpStdioClient,
        ctx: RunnerContext,
        session_id: str,
        prompt_blocks: list[dict[str, typing.Any]],
        *,
        timeout: float,
        streaming: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        prompt_request = client.send_request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": prompt_blocks,
            },
        )

        sequence = 0
        final_text_parts: list[str] = []
        active_message_id = ""
        active_tool_calls: dict[str, str] = {}
        deadline = time.monotonic() + timeout

        while True:
            if prompt_request.future.done():
                update = client.next_update_nowait()
                if update is None:
                    break
            else:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                update = await client.next_update(timeout=0.1)
                if update is None:
                    continue

            text = _agent_text_from_update(update)
            if text:
                message_id = _agent_message_id(update)
                if message_id:
                    if active_message_id and message_id != active_message_id:
                        final_text_parts.clear()
                    active_message_id = message_id
                final_text_parts.append(text)
                if streaming:
                    sequence += 1
                    yield RunnerResult.message_delta(
                        ctx.run_id,
                        MessageChunk(
                            role="assistant",
                            content=text,
                            all_content="".join(final_text_parts),
                            msg_sequence=sequence,
                        ),
                    )

            tool_payload = _tool_update_payload(update)
            if tool_payload:
                tool_call_id = str(tool_payload.get("toolCallId") or tool_payload.get("id") or "")
                observed_tool_name = _tool_update_name(tool_payload)
                status = str(tool_payload.get("status") or "")
                if tool_call_id and tool_call_id not in active_tool_calls:
                    active_tool_calls[tool_call_id] = observed_tool_name
                    tool_name = observed_tool_name
                    yield RunnerResult.tool_call_started(ctx.run_id, tool_call_id, tool_name, {})
                if tool_call_id and status in {"completed", "failed", "cancelled"}:
                    tool_name = active_tool_calls.get(tool_call_id, observed_tool_name)
                    yield RunnerResult.tool_call_completed(
                        ctx.run_id,
                        tool_call_id,
                        tool_name,
                        result=tool_payload if status == "completed" else None,
                        error=None if status == "completed" else json.dumps(tool_payload, ensure_ascii=False),
                    )

        await prompt_request.wait(timeout=timeout)
        final_text = "".join(final_text_parts).strip()
        if not final_text:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error="ACP agent returned no assistant text",
                code="acp.empty_response",
            )
            return

        yield RunnerResult.message_completed(ctx.run_id, Message(role="assistant", content=final_text))
        yield RunnerResult.run_completed(ctx.run_id, finish_reason="stop")

    def _daemon_payload(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        prompt_text: str,
        stored_session_id: str,
    ) -> dict[str, typing.Any]:
        return {
            "run_id": ctx.run_id,
            "prompt_text": prompt_text,
            "input": ctx.input.model_dump(mode="json") if hasattr(ctx.input, "model_dump") else {},
            "input_text": self._input_text(ctx),
            "config": {
                "provider": config["provider"],
                "acp_command": config["acp_command"],
                "workspace": config["workspace"],
                "cwd": config["workspace"] or None,
                "session_cwd": config["session_cwd"],
                "env": config["env"],
                "timeout": config["timeout"],
                "startup_timeout": config["startup_timeout"],
                "initialize_timeout": config["initialize_timeout"],
                "reuse_session": config["reuse_session"],
                "create_session_if_missing": config["create_session_if_missing"],
                "streaming": config["streaming"],
                "permission_decision": config["permission_decision"],
                "stored_session_id": stored_session_id,
                "mcp_servers": config["mcp_servers"],
                "langbot_assets_enabled": config["mcp_bridge_enabled"],
                "mcp_request_timeout": config["mcp_bridge_request_timeout"],
            },
        }

    async def _run_daemon(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        prompt_text: str,
        stored_session_id: str,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        hub = get_agent_runtime_daemon_hub("acp", error_code_prefix="acp")
        await hub.start(
            host=config["daemon_hub"]["host"],
            port=config["daemon_hub"]["port"],
            token=config["daemon_hub"]["token"],
        )

        await hub.wait_for_daemon(config["daemon_id"], config["daemon_connect_timeout"])
        tools = AgentRunExternalTools(self.get_run_api(ctx), ctx) if config["mcp_bridge_enabled"] else None
        payload = self._daemon_payload(ctx, config, prompt_text, stored_session_id)
        async with contextlib.aclosing(
            hub.run_job(
                daemon_id=config["daemon_id"],
                payload=payload,
                tools=tools,
                timeout=config["timeout"],
            )
        ) as event_stream:
            async for event in event_stream:
                event.setdefault("run_id", ctx.run_id)
                yield RunnerResult.model_validate(event)

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        try:
            config = self._validate_config(ctx)
        except AcpError as exc:
            yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)
            return

        input_text = self._input_text(ctx)
        if not has_acp_prompt_input(input_text, ctx.input):
            yield RunnerResult.run_failed(ctx.run_id, error="input text is required", code="acp.empty_input")
            return

        prompt_text = self._with_run_scope_prompt(ctx, input_text) if config["append_run_scope_prompt"] else input_text

        # The first turn carries the run-scope system prompt and the original
        # multimodal input; steering follow-ups are plain text resumed against the
        # same agent session (the Host queues them while this run is active).
        first_turn = {"value": True}

        def run_turn(turn_prompt: str, resume_session_id: str) -> typing.AsyncGenerator[RunnerResult, None]:
            if first_turn["value"]:
                first_turn["value"] = False
                return self._run_acp_turn(ctx, config, turn_prompt, resume_session_id, ctx.input)
            return self._run_acp_turn(ctx, config, turn_prompt, resume_session_id, AgentInput(text=turn_prompt))

        initial_resume = self._stored_session_id(ctx) if config["reuse_session"] else ""
        async for result in run_with_steering(
            ctx,
            lambda: self.get_run_api(ctx),
            run_turn,
            initial_prompt=prompt_text,
            initial_resume_session_id=initial_resume,
            session_state_key=ACP_SESSION_STATE_KEY,
        ):
            yield result

    async def _run_acp_turn(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        prompt_text: str,
        resume_session_id: str,
        agent_input: AgentInput,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        """Run a single ACP prompt turn, resuming ``resume_session_id`` when set."""
        stored_session_id = resume_session_id or (self._stored_session_id(ctx) if config["reuse_session"] else "")

        if config["location"] == "daemon":
            try:
                async for result in self._run_daemon(ctx, config, prompt_text, stored_session_id):
                    yield result
            except AgentRuntimeDaemonError as exc:
                yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)
            except Exception as exc:
                logger.exception("ACP daemon transport failed: %s", exc)
                yield RunnerResult.run_failed(ctx.run_id, error=str(exc), code="acp.daemon_unexpected")
            return

        access = None
        client: AcpStdioClient | None = None
        try:
            access, mcp_servers = self._mcp_servers(ctx, config)
            launch_config = self._launch_config(config, access)
            client = AcpStdioClient(
                command=launch_config["command"],
                args=launch_config["args"],
                cwd=launch_config["cwd"],
                env=config["env"],
                unset_env=launch_config["unset_env"],
                permission_decision=config["permission_decision"],
                startup_timeout=config["startup_timeout"],
            )
            async with client:
                initialize_result = await client.initialize(timeout=config["initialize_timeout"])
                session_id, created = await self._create_or_resume_session(
                    client,
                    initialize_result,
                    ctx,
                    config,
                    mcp_servers,
                    stored_session_id,
                )

                if created or stored_session_id != session_id:
                    yield RunnerResult.state_updated(
                        ctx.run_id,
                        ACP_SESSION_STATE_KEY,
                        session_id,
                        scope="conversation",
                    )

                prompt_blocks = acp_prompt_blocks(prompt_text, agent_input, prompt_capabilities(initialize_result))
                async for result in self._stream_prompt_results(
                    client,
                    ctx,
                    session_id,
                    prompt_blocks,
                    timeout=config["timeout"],
                    streaming=config["streaming"],
                ):
                    yield result

        except AcpError as exc:
            if client and client.stderr_tail.strip():
                logger.warning("ACP runner failed with stderr tail: %s", client.stderr_tail.strip())
            yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)
        except TimeoutError:
            yield RunnerResult.run_failed(ctx.run_id, error="ACP request timed out", code="acp.timeout", retryable=True)
        except Exception as exc:
            logger.exception("ACP runner unexpected error: %s", exc)
            yield RunnerResult.run_failed(ctx.run_id, error=f"ACP runner error: {exc}", code="acp.unexpected_error")
        finally:
            if access is not None:
                access.stop()
