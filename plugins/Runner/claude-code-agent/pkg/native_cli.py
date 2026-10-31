"""Native CLI runner helpers for Claude Code."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import re
import shlex
import tempfile
import time
import typing
import uuid

import pydantic
from langbot_plugin.api.agent_tools.decorators import agent_tool
from langbot_plugin.api.agent_tools.external_tools import AgentRunExternalTools
from langbot_plugin.api.agent_tools.mcp_access import AgentRunMCPAccess
from langbot_plugin.api.agent_tools.mcp_config import AgentMCPServerConfig
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner import (
    InteractionAction,
    InteractionField,
    InteractionOption,
    InteractionRequest,
    InteractionSubmission,
    RunnerContext,
    RunnerResult,
)

from pkg.daemon_relay import (
    AgentRuntimeDaemonClient,
    AgentRuntimeDaemonError,
    agent_runtime_daemon_config_from_plugin_config,
    get_agent_runtime_daemon_hub,
)
from pkg.runtime_support import local_workspace, terminate_process_group
from pkg.steering import run_with_steering

SESSION_STATE_KEY = "external.claude_code_session_id"
PENDING_INTERACTION_STATE_KEY = "external.claude_code_pending_interaction"
SUPPORTED_LOCATIONS = {"local", "remote-ssh", "daemon"}


_AUTH_ASSIGNMENT_RE = re.compile(r"(?i)(\bAuthorization\b[\"']?\s*[:=]\s*[\"']?)(?:Bearer\s+)?[^\"'\s,}\]]+")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:run[_-]?token|mcp[_-]?token|langbot_agent_mcp_token|"
    r"langbot[_-]?asset[_-]?run[_-]?token|api[_-]?key|secret|password)\b"
    r"[\"']?\s*[:=]\s*[\"']?)[^\"'\s,}\]]+"
)


def _redact_secrets(text: str) -> str:
    redacted = _AUTH_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", str(text))
    redacted = _BEARER_RE.sub("Bearer [REDACTED]", redacted)
    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)


class NativeCliError(Exception):
    def __init__(self, message: str, *, code: str = "claude_code.error", retryable: bool = False) -> None:
        redacted_message = _redact_secrets(message)
        super().__init__(redacted_message)
        self.message = redacted_message
        self.code = code
        self.retryable = retryable


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
    if os.name != "nt":
        return shlex.split(text)
    return [
        part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part for part in shlex.split(text, posix=False)
    ]


def _parse_json_object(value: typing.Any, *, label: str) -> dict[str, typing.Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise NativeCliError(f"{label} must be a JSON object", code="claude_code.config_invalid") from exc
    if not isinstance(parsed, dict):
        raise NativeCliError(f"{label} must be a JSON object", code="claude_code.config_invalid")
    return parsed


def _parse_json_list(value: typing.Any, *, label: str) -> list[typing.Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return list(value)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise NativeCliError(f"{label} must be a JSON array", code="claude_code.config_invalid") from exc
    if not isinstance(parsed, list):
        raise NativeCliError(f"{label} must be a JSON array", code="claude_code.config_invalid")
    return parsed


def _parse_config_args(value: typing.Any) -> list[str]:
    if isinstance(value, str) and value.strip().startswith("["):
        return [str(item) for item in _parse_json_list(value, label="args-json")]
    if isinstance(value, list):
        return [str(item) for item in value]
    return _parse_args(value)


def _mcp_server_to_config(server: AgentMCPServerConfig) -> dict[str, typing.Any]:
    if server.transport == "http":
        return {
            "type": "http",
            "url": server.url,
            "headers": dict(server.headers),
        }
    return {
        "command": server.command,
        "args": list(server.args),
        "env": dict(server.env),
    }


def _mcp_config_json(servers: list[AgentMCPServerConfig], extra_servers: list[typing.Any]) -> str:
    mcp_servers: dict[str, typing.Any] = {}
    for server in servers:
        mcp_servers[server.name] = _mcp_server_to_config(server)
    for item in extra_servers:
        if isinstance(item, dict) and item.get("name"):
            server_name = str(item["name"])
            server_config = dict(item)
            server_config.pop("name", None)
            mcp_servers[server_name] = server_config
    return json.dumps({"mcpServers": mcp_servers}, ensure_ascii=False, separators=(",", ":"))


def _write_temp_mcp_config(mcp_config: str, *, directory: str | None = None) -> str:
    fd, path = tempfile.mkstemp(prefix="langbot-claude-mcp-", suffix=".json", dir=directory)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        else:
            os.chmod(path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            handle.write(mcp_config)
        return path
    except Exception:
        if fd >= 0:
            with contextlib.suppress(OSError):
                os.close(fd)
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise


def _prompt_stdin(prompt: str) -> bytes:
    return prompt.encode("utf-8")


def _remote_payload_line(value: str) -> bytes:
    return base64.b64encode(value.encode("utf-8")) + b"\n"


def _event_text(event: dict[str, typing.Any]) -> str:
    event_type = str(event.get("type") or event.get("event") or "")
    if event_type in {"session.started", "turn.started", "turn.completed", "mcp.server.started"}:
        return ""
    if isinstance(event.get("text"), str):
        return str(event["text"])
    if isinstance(event.get("content"), str):
        return str(event["content"])
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    if isinstance(event.get("result"), str):
        return str(event["result"])
    return ""


def _event_session_id(event: dict[str, typing.Any]) -> str:
    value = event.get("session_id") or event.get("sessionId")
    if value:
        return str(value)
    session = event.get("session")
    if isinstance(session, dict) and (session.get("id") or session.get("session_id")):
        return str(session.get("id") or session.get("session_id"))
    return ""


_MCP_CONFIG_ARG_PLACEHOLDER = "__LANGBOT_CLAUDE_MCP_CONFIG_PATH__"
_LANGBOT_MCP_ALLOWED_TOOLS = "ToolSearch,mcp__langbot_agent__*"
_LANGBOT_MCP_SYSTEM_PROMPT = (
    "LangBot MCP tools may be deferred tools in Claude Code. When ToolSearch is available "
    "in the current session, use it with select:<full_tool_name> before the first call to "
    "any mcp__langbot_agent__* tool, then call that tool directly. In coordinator mode, "
    "the main session may expose only delegation tools; delegate the MCP request to one "
    "worker and require that worker to perform the same ToolSearch-then-call flow. Never "
    "claim a LangBot tool result unless the direct or delegated tool call completed."
)


def _shell_join_with_mcp_placeholder(argv: list[str]) -> str:
    return " ".join('"$langbot_mcp_config"' if arg == _MCP_CONFIG_ARG_PLACEHOLDER else shlex.quote(arg) for arg in argv)


def _remote_shell_command(
    workspace: str, argv: list[str], env: dict[str, str], *, read_mcp_from_stdin: bool = False
) -> str:
    parts = ["set -e"]
    parts.extend(f"export {shlex.quote(key)}={shlex.quote(value)}" for key, value in env.items())
    if workspace:
        quoted_workspace = shlex.quote(workspace)
        parts.append(f"mkdir -p {quoted_workspace}")
        parts.append(f"cd {quoted_workspace}")
    if read_mcp_from_stdin:
        parts.extend(
            [
                'langbot_mcp_config="$(mktemp "${TMPDIR:-/tmp}/langbot-claude-mcp.XXXXXX.json")"',
                'chmod 600 "$langbot_mcp_config"',
                "trap 'rm -f \"$langbot_mcp_config\"' EXIT",
                'IFS= read -r langbot_mcp_config_b64 || langbot_mcp_config_b64=""',
                '[ -n "$langbot_mcp_config_b64" ] && printf %s "$langbot_mcp_config_b64" | base64 -d > "$langbot_mcp_config" || printf %s "{}" > "$langbot_mcp_config"',
            ]
        )
    exec_prefix = "" if read_mcp_from_stdin else "exec "
    parts.append(f"{exec_prefix}{_shell_join_with_mcp_placeholder(argv)}")
    return f"bash -lc {shlex.quote(chr(10).join(parts))}"


def _input_text(ctx: RunnerContext) -> str:
    return ctx.input.to_text().strip()


def _claude_question_tool_use(event: dict[str, typing.Any]) -> tuple[str, dict[str, typing.Any]] | None:
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, dict):
            continue
        tool_name = str(block.get("name") or "")
        recognized_name = tool_name in {"AskUserQuestion", "ask_user_question"} or tool_name.endswith(
            "__ask_user_question"
        )
        if block.get("type") != "tool_use" or not recognized_name:
            continue
        tool_use_id = str(block.get("id") or "").strip()
        tool_input = block.get("input")
        if tool_use_id and isinstance(tool_input, dict):
            return tool_use_id, tool_input
    return None


def _interaction_from_claude_tool(
    tool_use_id: str,
    tool_input: dict[str, typing.Any],
) -> tuple[InteractionRequest, dict[str, typing.Any]]:
    raw_questions = tool_input.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise NativeCliError("AskUserQuestion requires at least one question", code="claude_code.interaction_invalid")

    fields: list[InteractionField] = []
    continuation_questions: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, raw_question in enumerate(raw_questions[:20], start=1):
        question = raw_question if isinstance(raw_question, dict) else {}
        field_id = str(question.get("id") or f"question_{index}").strip()[:128]
        if not field_id or field_id in seen_ids:
            field_id = f"question_{index}"
        seen_ids.add(field_id)
        label = str(question.get("question") or question.get("header") or f"Question {index}").strip()[:512]
        options: list[InteractionOption] = []
        raw_options = question.get("options")
        if isinstance(raw_options, list):
            for option_index, raw_option in enumerate(raw_options[:100], start=1):
                option = raw_option if isinstance(raw_option, dict) else {"label": raw_option}
                option_label = str(option.get("label") or f"Option {option_index}").strip()
                if not option_label:
                    continue
                options.append(
                    InteractionOption(
                        value=option_label[:512],
                        label=option_label[:512],
                        description=(str(option["description"])[:2000] if option.get("description") else None),
                    )
                )
        multiple = bool(question.get("multiSelect") or question.get("multiple"))
        field_type = "multiselect" if options and multiple else "select" if options else "text"
        fields.append(
            InteractionField(
                id=field_id,
                label=label,
                type=field_type,
                required=True,
                options=options,
            )
        )
        continuation_questions.append({"id": field_id, "question": label})

    title = str(tool_input.get("title") or "User input required").strip()[:1000]
    interaction_id = f"claude-{tool_use_id}"[:255]
    request = InteractionRequest(
        interaction_id=interaction_id,
        kind="form",
        title=title,
        description=(str(tool_input.get("description") or "").strip()[:10000] or None),
        fields=fields,
        actions=[InteractionAction(id="submit", label="Submit", style="primary")],
        fallback_text=f"{title}: " + "; ".join(field.label for field in fields),
    )
    continuation = {
        "version": 1,
        "interaction_id": interaction_id,
        "tool_use_id": tool_use_id,
        "questions": continuation_questions,
    }
    return request, continuation


def _pending_interaction(ctx: RunnerContext) -> dict[str, typing.Any] | None:
    value = ctx.state.conversation.get(PENDING_INTERACTION_STATE_KEY)
    return dict(value) if isinstance(value, dict) else None


def _submission_payload(
    submission: InteractionSubmission,
    continuation: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    if submission.interaction_id != continuation.get("interaction_id"):
        raise NativeCliError(
            "interaction submission does not match the pending Claude request",
            code="claude_code.interaction_mismatch",
        )
    question_by_id = {
        str(item.get("id")): str(item.get("question") or item.get("id"))
        for item in continuation.get("questions", [])
        if isinstance(item, dict) and item.get("id")
    }
    return {
        "action": submission.action_id,
        "answers": [
            {"id": field_id, "question": question_by_id.get(field_id, field_id), "answer": value}
            for field_id, value in submission.values.items()
        ],
    }


def _interaction_resume_prompt(payload: dict[str, typing.Any]) -> str:
    return (
        "The user answered the previously paused ask_user_question call. "
        "Treat these values as the authoritative response and continue the interrupted task.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


class ClaudeQuestionOption(pydantic.BaseModel):
    label: str = pydantic.Field(min_length=1, max_length=512)
    description: str | None = pydantic.Field(default=None, max_length=2000)

    model_config = pydantic.ConfigDict(extra="forbid")


class ClaudeQuestion(pydantic.BaseModel):
    id: str | None = pydantic.Field(default=None, max_length=128)
    question: str = pydantic.Field(min_length=1, max_length=512)
    header: str | None = pydantic.Field(default=None, max_length=512)
    options: list[ClaudeQuestionOption] = pydantic.Field(default_factory=list, max_length=100)
    multi_select: bool = pydantic.Field(default=False, alias="multiSelect")

    model_config = pydantic.ConfigDict(extra="forbid", populate_by_name=True)


class AskUserQuestionArgs(pydantic.BaseModel):
    title: str | None = pydantic.Field(default=None, max_length=1000)
    description: str | None = pydantic.Field(default=None, max_length=10000)
    questions: list[ClaudeQuestion] = pydantic.Field(min_length=1, max_length=20)

    model_config = pydantic.ConfigDict(extra="forbid")


class ClaudeCodeExternalTools(AgentRunExternalTools):
    def __init__(
        self,
        api: typing.Any,
        ctx: RunnerContext,
        *,
        include_assets: bool,
    ) -> None:
        self.include_assets = include_assets
        super().__init__(api, ctx)

    def _available_tool_names(self) -> set[str]:
        names = super()._available_tool_names() if self.include_assets else set()
        names.add("ask_user_question")
        return names

    @agent_tool(
        name="ask_user_question",
        description=(
            "Ask the user one or more questions through the LangBot conversation surface. "
            "Use this when work cannot continue without a user choice, confirmation, or value. "
            "The current run pauses until LangBot receives the user's response."
        ),
        args_model=AskUserQuestionArgs,
    )
    async def ask_user_question(self, args: AskUserQuestionArgs) -> dict[str, typing.Any]:
        return {"status": "paused", "question_count": len(args.questions)}


class NativeClaudeCodeRunner(Runner):
    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        data = ctx.config or {}
        location = str(data.get("location", "local") or "local").strip()
        if location not in SUPPORTED_LOCATIONS:
            raise NativeCliError("location must be local, remote-ssh, or daemon", code="claude_code.config_invalid")
        workspace = str(data.get("workspace") or "").strip()
        workspace = local_workspace(workspace) if location == "local" else workspace or os.getcwd()
        ssh_target = str(data.get("ssh-target") or data.get("ssh_target") or "").strip()
        if location == "remote-ssh" and not ssh_target:
            raise NativeCliError("ssh-target is required when location=remote-ssh", code="claude_code.config_invalid")
        daemon_id = str(data.get("daemon-id") or data.get("daemon_id") or "").strip()
        if location == "daemon" and not daemon_id:
            raise NativeCliError("daemon-id is required when location=daemon", code="claude_code.config_invalid")
        if location == "daemon" and os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            raise NativeCliError("daemon mode is unavailable in shared runtime", code="claude_code.config_invalid")
        return {
            "location": location,
            "workspace": workspace,
            "command": str(data.get("command") or "claude"),
            "args": _parse_config_args(data.get("args-json") or data.get("args")),
            "env": {str(k): str(v) for k, v in _parse_json_object(data.get("env-json"), label="env-json").items()},
            "ssh_target": ssh_target,
            "ssh_port": _to_int(data.get("ssh-port"), 22),
            "daemon_id": daemon_id,
            "daemon_connect_timeout": _to_float(data.get("daemon-connect-timeout"), 30.0),
            "timeout": _to_float(data.get("timeout"), 300.0),
            "streaming": _to_bool(data.get("streaming"), True),
            "reuse_session": _to_bool(data.get("reuse-session"), True),
            "dangerously_skip_permissions": _to_bool(data.get("dangerously-skip-permissions"), True),
            "langbot_assets_enabled": _to_bool(data.get("langbot-assets-enabled"), True),
            "mcp_bridge_transport": str(data.get("mcp-bridge-transport", "auto") or "auto").strip(),
            "mcp_servers": _parse_json_list(data.get("mcp-servers-json"), label="mcp-servers-json"),
            "daemon_hub": agent_runtime_daemon_config_from_plugin_config(
                self.get_plugin_config(),
                env_prefix="LANGBOT_CLAUDE_CODE_DAEMON",
                default_port=8767,
            ),
        }

    def _stored_session_id(self, ctx: RunnerContext) -> str:
        return str(ctx.state.conversation.get(SESSION_STATE_KEY) or "").strip()

    def _session_id(self, ctx: RunnerContext, config: dict[str, typing.Any]) -> tuple[str, bool]:
        stored = self._stored_session_id(ctx)
        if stored and config["reuse_session"]:
            return stored, False
        return str(uuid.uuid4()), True

    def _argv(
        self,
        config: dict[str, typing.Any],
        *,
        session_id: str,
        mcp_config_path: str,
        resume: bool,
    ) -> list[str]:
        argv = [*_parse_args(config["command"]), *config["args"], "-p", "--verbose", "--output-format", "stream-json"]
        if config.get("dangerously_skip_permissions", True) and "--dangerously-skip-permissions" not in argv:
            argv.append("--dangerously-skip-permissions")
        argv.extend(["--allowedTools", _LANGBOT_MCP_ALLOWED_TOOLS])
        if mcp_config_path:
            argv.extend(["--append-system-prompt", _LANGBOT_MCP_SYSTEM_PROMPT])
            argv.extend(["--strict-mcp-config", "--mcp-config", mcp_config_path])
        if session_id:
            # `--session-id` only creates a new session; continuing an existing
            # one (stored reuse or steering follow-up) requires `--resume`.
            argv.extend(["--resume", session_id] if resume else ["--session-id", session_id])
        return argv

    def _mcp_access(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
    ) -> tuple[AgentRunMCPAccess, ClaudeCodeExternalTools]:
        run_api = self.get_run_api(ctx)
        tools = ClaudeCodeExternalTools(
            run_api,
            ctx,
            include_assets=config["langbot_assets_enabled"],
        )
        access = AgentRunMCPAccess(
            run_api,
            ctx,
            enabled=True,
            location=config["location"],
            mode="ephemeral",
            transport=config["mcp_bridge_transport"],
            bridge_request_timeout=config["timeout"],
            tools=tools,
        )
        access.start()
        return access, tools

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        try:
            config = self._validate_config(ctx)
            submission = ctx.input.interaction
            if submission is not None:
                continuation = _pending_interaction(ctx)
                if continuation is None:
                    raise NativeCliError(
                        "pending Claude interaction state was not found",
                        code="claude_code.interaction_not_found",
                    )
                tool_use_id = str(continuation.get("tool_use_id") or "").strip()
                if not tool_use_id:
                    raise NativeCliError(
                        "pending Claude interaction has no tool_use_id",
                        code="claude_code.interaction_invalid",
                    )
                prompt = _interaction_resume_prompt(_submission_payload(submission, continuation))
                yield RunnerResult.state_updated(
                    ctx.run_id,
                    PENDING_INTERACTION_STATE_KEY,
                    None,
                    scope="conversation",
                )
            else:
                prompt = _input_text(ctx)
                if not prompt:
                    raise NativeCliError("input text is required", code="claude_code.empty_input")
            session_id, session_created = self._session_id(ctx, config)
            if session_created:
                yield RunnerResult.state_updated(ctx.run_id, SESSION_STATE_KEY, session_id, scope="conversation")

            # The first turn resumes only when reusing a stored session; every
            # turn after the first continues the session created/resumed above.
            resume_state = {"resume": not session_created}

            def run_turn(turn_prompt: str, resume_session_id: str) -> typing.AsyncGenerator[RunnerResult, None]:
                resume = resume_state["resume"]
                resume_state["resume"] = True
                if config["location"] == "daemon":
                    return self._run_daemon(ctx, config, turn_prompt, resume_session_id, resume)
                return self._run_local_or_ssh(ctx, config, turn_prompt, resume_session_id, resume)

            async for result in run_with_steering(
                ctx,
                lambda: self.get_run_api(ctx),
                run_turn,
                initial_prompt=prompt,
                initial_resume_session_id=session_id,
                session_state_key=SESSION_STATE_KEY,
            ):
                yield result
        except NativeCliError as exc:
            yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)
        except AgentRuntimeDaemonError as exc:
            yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)

    async def _run_local_or_ssh(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        prompt: str,
        session_id: str,
        resume: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        access, tools = self._mcp_access(ctx, config)
        mcp_config_path = ""
        try:
            mcp_servers = [access.server_config] if access.server_config else []
            mcp_config = (
                _mcp_config_json(mcp_servers, config["mcp_servers"]) if mcp_servers or config["mcp_servers"] else ""
            )
            if mcp_config and config["location"] == "local":
                mcp_config_path = _write_temp_mcp_config(mcp_config)
            elif mcp_config:
                mcp_config_path = _MCP_CONFIG_ARG_PLACEHOLDER
            argv = self._argv(
                config,
                session_id=session_id,
                mcp_config_path=mcp_config_path,
                resume=resume,
            )
            env = {**os.environ, **config["env"]}
            command = argv[0]
            args = argv[1:]
            cwd = config["workspace"] if config["location"] == "local" else None
            initial_stdin = _prompt_stdin(prompt)
            if config["location"] == "remote-ssh":
                ssh_args = ["-T", "-p", str(config["ssh_port"])]
                if access.reverse_tunnel:
                    ssh_args.extend(access.reverse_tunnel.ssh_args())
                initial_stdin = (_remote_payload_line(mcp_config) if mcp_config else b"") + _prompt_stdin(prompt)
                ssh_args.extend(
                    [
                        config["ssh_target"],
                        _remote_shell_command(
                            config["workspace"],
                            argv,
                            config["env"],
                            read_mcp_from_stdin=bool(mcp_config),
                        ),
                    ]
                )
                command = "ssh"
                args = ssh_args
            async with contextlib.aclosing(
                _run_cli_process(
                    ctx,
                    command,
                    args,
                    cwd=cwd,
                    env=env,
                    timeout=config["timeout"],
                    streaming=config["streaming"],
                    expected_session_id=session_id,
                    initial_stdin=initial_stdin,
                )
            ) as event_stream:
                async for result in event_stream:
                    yield result
        finally:
            if mcp_config_path and mcp_config_path != _MCP_CONFIG_ARG_PLACEHOLDER:
                with contextlib.suppress(OSError):
                    os.unlink(mcp_config_path)
            access.stop()

    async def _run_daemon(
        self,
        ctx: RunnerContext,
        config: dict[str, typing.Any],
        prompt: str,
        session_id: str,
        resume: bool,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        hub = get_agent_runtime_daemon_hub("claude-code", error_code_prefix="claude_code")
        await hub.start(
            host=config["daemon_hub"]["host"],
            port=config["daemon_hub"]["port"],
            token=config["daemon_hub"]["token"],
        )
        tools = ClaudeCodeExternalTools(
            self.get_run_api(ctx),
            ctx,
            include_assets=config["langbot_assets_enabled"],
        )
        await hub.wait_for_daemon(config["daemon_id"], config["daemon_connect_timeout"])
        payload = {
            "prompt": prompt,
            "session_id": session_id,
            "resume": resume,
            "config": {
                "command": config["command"],
                "args": config["args"],
                "workspace": config["workspace"],
                "env": config["env"],
                "timeout": config["timeout"],
                "streaming": config["streaming"],
                "dangerously_skip_permissions": config["dangerously_skip_permissions"],
                "mcp_servers": config["mcp_servers"],
                "langbot_assets_enabled": config["langbot_assets_enabled"],
            },
        }
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


class NativeClaudeCodeDaemon(AgentRuntimeDaemonClient):
    async def run_job(self, job_id: str, payload: dict[str, typing.Any]) -> None:
        proxy = None
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        try:
            mcp_servers: list[AgentMCPServerConfig] = []
            proxy = self.create_mcp_proxy(job_id, request_timeout=float(config.get("timeout") or 300.0))
            proxy.start()
            mcp_servers.append(proxy.mcp_server())
            mcp_config = _mcp_config_json(mcp_servers, list(config.get("mcp_servers") or [])) if mcp_servers else ""
            mcp_config_path = _write_temp_mcp_config(mcp_config) if mcp_config else ""
            argv = [
                *_parse_args(config.get("command") or "claude"),
                *list(config.get("args") or []),
                "-p",
                "--verbose",
                "--output-format",
                "stream-json",
            ]
            if config.get("dangerously_skip_permissions", True) and "--dangerously-skip-permissions" not in argv:
                argv.append("--dangerously-skip-permissions")
            argv.extend(["--allowedTools", _LANGBOT_MCP_ALLOWED_TOOLS])
            if mcp_config_path:
                argv.extend(["--append-system-prompt", _LANGBOT_MCP_SYSTEM_PROMPT])
                argv.extend(["--strict-mcp-config", "--mcp-config", mcp_config_path])
            session_id = str(payload.get("session_id") or "")
            if session_id:
                # See NativeClaudeCodeRunner._argv: resume continues, session-id creates.
                argv.extend(["--resume", session_id] if payload.get("resume") else ["--session-id", session_id])
            try:
                async with contextlib.aclosing(
                    _run_cli_process_events(
                        argv[0],
                        argv[1:],
                        cwd=str(config.get("workspace") or os.getcwd()),
                        env={**os.environ, **{str(k): str(v) for k, v in dict(config.get("env") or {}).items()}},
                        timeout=float(config.get("timeout") or 300.0),
                        streaming=bool(config.get("streaming", True)),
                        expected_session_id=session_id,
                        initial_stdin=_prompt_stdin(str(payload.get("prompt") or "")),
                    )
                ) as event_stream:
                    async for event in event_stream:
                        await self.emit_event(job_id, event)
            except NativeCliError as exc:
                await self.emit_event(
                    job_id,
                    {
                        "type": "run.failed",
                        "data": {"error": exc.message, "code": exc.code, "retryable": exc.retryable},
                    },
                )
            finally:
                if mcp_config_path:
                    with contextlib.suppress(OSError):
                        os.unlink(mcp_config_path)
        finally:
            if proxy is not None:
                proxy.stop()


async def _run_cli_process(
    ctx: RunnerContext,
    command: str,
    args: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout: float,
    streaming: bool,
    expected_session_id: str,
    initial_stdin: bytes = b"",
) -> typing.AsyncGenerator[RunnerResult, None]:
    try:
        async with contextlib.aclosing(
            _run_cli_process_events(
                command,
                args,
                cwd=cwd,
                env=env,
                timeout=timeout,
                streaming=streaming,
                expected_session_id=expected_session_id,
                initial_stdin=initial_stdin,
            )
        ) as event_stream:
            async for event in event_stream:
                event.setdefault("run_id", ctx.run_id)
                yield RunnerResult.model_validate(event)
    except NativeCliError as exc:
        yield RunnerResult.run_failed(ctx.run_id, error=exc.message, code=exc.code, retryable=exc.retryable)


async def _run_cli_process_events(
    command: str,
    args: list[str],
    *,
    cwd: str | None,
    env: dict[str, str],
    timeout: float,
    streaming: bool,
    expected_session_id: str,
    initial_stdin: bytes = b"",
) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
    try:
        process = await asyncio.create_subprocess_exec(
            command,
            *args,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE if initial_stdin else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=os.name != "nt",
        )
    except FileNotFoundError as exc:
        raise NativeCliError(f"Claude Code command not found: {command}", code="claude_code.command_not_found") from exc
    except PermissionError as exc:
        raise NativeCliError(
            f"Claude Code command is not executable: {command}", code="claude_code.permission_denied"
        ) from exc
    except OSError as exc:
        raise NativeCliError(f"Failed to start Claude Code command: {exc}", code="claude_code.start_failed") from exc
    assert process.stdout is not None
    assert process.stderr is not None
    deadline = time.monotonic() + timeout
    sequence = 0
    final_parts: list[str] = []
    pending_interaction: tuple[InteractionRequest, dict[str, typing.Any]] | None = None
    terminal_result_text = ""
    stderr_task = asyncio.create_task(process.stderr.read())
    try:
        if initial_stdin:
            assert process.stdin is not None
            process.stdin.write(initial_stdin)
            await process.stdin.drain()
            process.stdin.close()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                raise NativeCliError("Claude Code run timed out", code="claude_code.timeout", retryable=True)
            line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            parsed = _parse_cli_event(text)
            if parsed.get("type") == "error":
                raise NativeCliError(
                    str(parsed.get("message") or parsed), code=str(parsed.get("code") or "claude_code.cli_error")
                )
            session_id = _event_session_id(parsed)
            if session_id and session_id != expected_session_id:
                yield {
                    "type": "state.updated",
                    "data": {"key": SESSION_STATE_KEY, "value": session_id, "scope": "conversation"},
                }
            question_tool = _claude_question_tool_use(parsed)
            if question_tool is not None and pending_interaction is None:
                tool_use_id, tool_input = question_tool
                pending_interaction = _interaction_from_claude_tool(tool_use_id, tool_input)
                continue
            chunk = _event_text(parsed)
            if parsed.get("type") == "result" and chunk:
                terminal_result_text = chunk
                continue
            if chunk and pending_interaction is None:
                final_parts.append(chunk)
                if streaming:
                    sequence += 1
                    yield {
                        "type": "message.delta",
                        "sequence": sequence,
                        "data": {
                            "chunk": {
                                "role": "assistant",
                                "content": chunk,
                                "all_content": "".join(final_parts),
                                "msg_sequence": sequence,
                            }
                        },
                    }
        returncode = await asyncio.wait_for(process.wait(), timeout=max(0.1, deadline - time.monotonic()))
        stderr = _redact_secrets((await stderr_task).decode("utf-8", errors="replace").strip())
        if returncode != 0:
            raise NativeCliError(
                stderr or f"Claude Code exited with status {returncode}", code="claude_code.process_failed"
            )
        if pending_interaction is not None:
            request, continuation = pending_interaction
            yield {
                "type": "state.updated",
                "data": {
                    "key": PENDING_INTERACTION_STATE_KEY,
                    "value": continuation,
                    "scope": "conversation",
                },
            }
            yield {
                "type": "action.requested",
                "data": {
                    "action": "interaction.requested",
                    "payload": request.model_dump(mode="json"),
                },
            }
            return
        final_text = (terminal_result_text or "".join(final_parts)).strip()
        if not final_text:
            raise NativeCliError("Claude Code returned no assistant text", code="claude_code.empty_response")
        final_message = {"role": "assistant", "content": final_text}
        if streaming:
            sequence += 1
            yield {
                "type": "message.delta",
                "sequence": sequence,
                "data": {
                    "chunk": {
                        "role": "assistant",
                        "content": final_text,
                        "all_content": final_text,
                        "is_final": True,
                        "msg_sequence": sequence,
                    }
                },
            }
        else:
            yield {"type": "message.completed", "data": {"message": final_message}}
        yield {"type": "run.completed", "data": {"finish_reason": "stop"}}
    finally:
        await terminate_process_group(process)
        if not stderr_task.done():
            stderr_task.cancel()
        await asyncio.gather(stderr_task, return_exceptions=True)


def _parse_cli_event(line: str) -> dict[str, typing.Any]:
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {"type": "message.completed", "text": line}
    return parsed if isinstance(parsed, dict) else {"type": "message.completed", "text": line}
