"""Multica Agent runner: chat with a Multica agent from LangBot.

Each LangBot conversation is mapped to one Multica chat session. A user
message is posted to that session, which enqueues a task for the selected
Multica agent; the runner polls until the agent's reply for that task is
written back and returns it as the LangBot reply.

While waiting, the runner can report the task lifecycle (submitted, started,
still running) as separate messages or as one streamed message. Multica has no
task event stream, so step-level progress is not available.

Conversation-scoped state:
- multica.agent_id / multica.agent_name: agent chosen in chat with ``<prefix> use``; overrides config.
- multica.agent_resolved: ``{query, id, name}`` cache of the configured agent name.
- multica.agent_choices: ``{items, expires_at}`` numbered list behind ``<prefix> use <number>``.
- multica.session_id: Multica chat session bound to this conversation.
- multica.session_agent_id: agent the stored session was created for.
"""

from __future__ import annotations

import asyncio
import logging
import time
import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.runner import RunnerContext, RunnerResult
from pkg.endpoint import endpoint
from pkg.errors import MulticaAPIError, MulticaConfigError
from pkg.multica_client import (
    MAX_LISTED_NAMES,
    TASK_RUNNING,
    AgentResolutionError,
    AsyncMulticaClient,
    is_uuid,
    match_agents,
    short_id,
)

logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = "https://api.multica.ai"
STATE_AGENT = "multica.agent_id"
STATE_AGENT_NAME = "multica.agent_name"
STATE_RESOLVED = "multica.agent_resolved"
STATE_CHOICES = "multica.agent_choices"
STATE_SESSION = "multica.session_id"
STATE_SESSION_AGENT = "multica.session_agent_id"

PROGRESS_MODES = ("off", "messages", "stream")
CHOICES_TTL = 600  # seconds a numbered agent list stays valid for "<prefix> use <number>"

# Indirection so tests can run the polling loop without real delays.
_sleep = asyncio.sleep
_monotonic = time.monotonic
_now = time.time


class DefaultRunner(Runner):
    """Forward LangBot messages to a Multica agent chat session."""

    # ------------------------------------------------------------------ config

    def _validate_config(self, ctx: RunnerContext) -> dict[str, typing.Any]:
        config = ctx.config or {}

        server_url = str(config.get("server-url") or DEFAULT_SERVER_URL).strip()
        try:
            endpoint(server_url)
        except ValueError as exc:
            raise MulticaConfigError(f"server-url is invalid: {exc}") from None

        token = str(config.get("api-token") or "").strip()
        if not token:
            raise MulticaConfigError("api-token is required (a Multica personal access token, mul_...)")

        workspace_id = str(config.get("workspace-id") or "").strip()
        if not workspace_id:
            raise MulticaConfigError("workspace-id is required")

        timeout = _number(config.get("timeout", 600), "timeout", 10, 3600)
        poll_interval = _number(config.get("poll-interval", 2), "poll-interval", 0.5, 60)
        request_timeout = _number(config.get("request-timeout", 30), "request-timeout", 1, 300)

        prefix = str(config.get("command-prefix") or "/multica").strip()

        progress_mode = str(config.get("progress-mode") or "messages").strip().lower()
        if progress_mode not in PROGRESS_MODES:
            raise MulticaConfigError(f"progress-mode must be one of: {', '.join(PROGRESS_MODES)}")
        progress_interval = _number(config.get("progress-interval", 15), "progress-interval", 5, 300)

        return {
            "server_url": server_url,
            "token": token,
            "workspace_id": workspace_id,
            # "agent" takes a name or UUID; the deprecated 0.1.x "agent-id" is an id used as-is.
            "agent": str(config.get("agent") or "").strip(),
            "legacy_agent_id": str(config.get("agent-id") or "").strip(),
            "allow_agent_switch": bool(config.get("allow-agent-switch", True)),
            "command_prefix": prefix,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "request_timeout": request_timeout,
            "progress_mode": progress_mode,
            "progress_interval": progress_interval,
        }

    def _make_client(self, config: dict[str, typing.Any]) -> AsyncMulticaClient:
        return AsyncMulticaClient(
            server_url=config["server_url"],
            token=config["token"],
            workspace_id=config["workspace_id"],
            timeout=config["request_timeout"],
        )

    # --------------------------------------------------------------------- run

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        try:
            config = self._validate_config(ctx)
        except MulticaConfigError as e:
            yield RunnerResult.run_failed(ctx.run_id, error=e.message, code=e.code)
            return

        client = self._make_client(config)
        text = (ctx.input.to_text() or "").strip()
        state = dict(ctx.state.conversation or {})

        try:
            command = _parse_command(text, config["command_prefix"])
            if command is not None:
                async for result in self._handle_command(ctx, client, config, state, *command):
                    yield result
                yield RunnerResult.run_completed(ctx.run_id)
                return

            if not text:
                yield RunnerResult.run_failed(ctx.run_id, error="Empty message", code="multica.empty_input")
                return

            try:
                agent_id, agent_name, updates = await self._select_agent(ctx.run_id, client, config, state)
            except AgentResolutionError as e:
                if e.candidates:
                    yield _choices_update(ctx.run_id, e.candidates)
                hint = (
                    f"用 {config['command_prefix']} use <序号> 或完整 ID 选择。"
                    if config["allow_agent_switch"]
                    else "请在运行器配置中填写更精确的名称或完整 ID。"
                )
                error = f"{e.message}{hint}" if e.candidates else e.message
                yield RunnerResult.run_failed(ctx.run_id, error=error, code=e.code)
                return
            for update in updates:
                yield update

            session_id = ""
            if state.get(STATE_SESSION_AGENT) == agent_id:
                session_id = str(state.get(STATE_SESSION) or "")

            created = False
            if not session_id:
                session_id = await client.create_session(agent_id, _session_title(ctx))
                created = True

            try:
                task_id = await client.send_message(session_id, text)
            except MulticaAPIError as e:
                # The stored session may have been deleted or archived in Multica.
                if created or e.status not in (400, 403, 404, 409, 410):
                    raise
                session_id = await client.create_session(agent_id, _session_title(ctx))
                created = True
                task_id = await client.send_message(session_id, text)

            if created:
                yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION, session_id, scope="conversation")
                yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION_AGENT, agent_id, scope="conversation")

            progress = _Progress(ctx.run_id, config["progress_mode"], config["progress_interval"])
            label = agent_name or short_id(agent_id)
            for result in progress.emit(f"⏳ 已提交给 {label}（任务 {short_id(task_id)}）"):
                yield result

            reply: dict[str, typing.Any] = {}
            try:
                async for item in self._wait_for_reply(ctx, client, config, session_id, task_id, progress, label):
                    if isinstance(item, RunnerResult):
                        yield item
                    else:
                        reply = item
            except MulticaAPIError as e:
                for result in progress.close(_failure_line(e.code)):
                    yield result
                raise

            if reply.get("failure_reason"):
                for result in progress.close(f"⚠️ {label} 运行失败"):
                    yield result
                yield RunnerResult.run_failed(
                    ctx.run_id,
                    error=f"Multica agent run failed: {reply.get('content') or reply['failure_reason']}",
                    code="multica.agent_failed",
                )
                return

            for result in progress.answer(str(reply.get("content") or "")):
                yield result
            yield RunnerResult.run_completed(ctx.run_id)
        except MulticaAPIError as e:
            yield RunnerResult.run_failed(ctx.run_id, error=e.message, code=e.code, retryable=e.retryable)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Multica runner unexpected error")
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"Multica runner error: {e.__class__.__name__}",
                code="multica.unexpected_error",
            )

    async def _select_agent(
        self,
        run_id: str,
        client: AsyncMulticaClient,
        config: dict[str, typing.Any],
        state: dict[str, typing.Any],
    ) -> tuple[str, str, list[RunnerResult]]:
        """Return the agent id and name for this conversation, plus state updates to persist."""
        if state.get(STATE_AGENT):
            return str(state[STATE_AGENT]), str(state.get(STATE_AGENT_NAME) or ""), []

        query = config["agent"]
        if not query and config["legacy_agent_id"]:
            return config["legacy_agent_id"], "", []
        if not query:
            raise MulticaConfigError(
                f"No Multica agent selected. Set agent (a name or UUID) in the runner config or send "
                f"'{config['command_prefix']} use <agent>'."
            )
        cached = state.get(STATE_RESOLVED)
        if isinstance(cached, dict) and cached.get("query") == query and cached.get("id"):
            return str(cached["id"]), str(cached.get("name") or ""), []
        if is_uuid(query):
            return query, "", []

        agent = await client.resolve_agent(query)
        resolved = {"query": query, "id": agent["id"], "name": agent["name"]}
        return (
            agent["id"],
            agent["name"],
            [RunnerResult.state_updated(run_id, STATE_RESOLVED, resolved, scope="conversation")],
        )

    async def _wait_for_reply(
        self,
        ctx: RunnerContext,
        client: AsyncMulticaClient,
        config: dict[str, typing.Any],
        session_id: str,
        task_id: str,
        progress: _Progress,
        label: str,
    ) -> typing.AsyncGenerator[RunnerResult | dict[str, typing.Any], None]:
        """Poll until the task's reply lands; yield progress results, then the reply row."""
        timeout = config["timeout"]
        host_deadline = getattr(ctx.runtime, "deadline_at", None) if ctx.runtime else None
        if host_deadline:
            # Leave a small margin so the failure is reported before the host cuts the run.
            timeout = max(1.0, min(timeout, float(host_deadline) - time.time() - 2))
        started_at = _monotonic()
        deadline = started_at + timeout
        running = False

        while True:
            await _sleep(config["poll_interval"])
            reply = _find_reply(await client.recent_messages(session_id), task_id)
            if reply is not None:
                yield reply
                return

            status = (await client.pending_tasks(session_id)).get(task_id)
            if status is None:
                # The task left the queue; its reply row may have landed between the reads.
                reply = _find_reply(await client.recent_messages(session_id), task_id)
                if reply is not None:
                    yield reply
                    return
                raise MulticaAPIError(
                    "The Multica agent task ended without a reply (it may have been cancelled).",
                    code="multica.no_reply",
                )

            now = _monotonic()
            if status == TASK_RUNNING and not running:
                running = True
                for result in progress.emit(f"▶️ {label} 开始执行"):
                    yield result
            elif progress.due(now):
                waited = int(now - started_at)
                line = f"⏱ 仍在执行 · 已等待 {waited}s" if running else f"⏱ 排队中 · 已等待 {waited}s"
                for result in progress.emit(line):
                    yield result

            if _monotonic() >= deadline:
                raise MulticaAPIError(
                    f"The Multica agent did not reply within {int(timeout)}s; "
                    "the task keeps running and its reply stays visible in Multica.",
                    code="multica.timeout",
                    retryable=True,
                )

    # ---------------------------------------------------------------- commands

    async def _handle_command(
        self,
        ctx: RunnerContext,
        client: AsyncMulticaClient,
        config: dict[str, typing.Any],
        state: dict[str, typing.Any],
        verb: str,
        arg: str,
    ) -> typing.AsyncGenerator[RunnerResult, None]:
        prefix = config["command_prefix"]
        current_id, current_name = _known_agent(config, state)

        if verb in ("agents", "find"):
            agents = await client.list_agents()
            if not current_id and config["agent"]:
                matches = match_agents(agents, config["agent"])
                if len(matches) == 1:
                    current_id = str(matches[0].get("id"))
            shown = agents
            if arg:
                keyword = arg.casefold()
                shown = [a for a in agents if keyword in str(a.get("name") or "").casefold()]
            if not agents:
                reply = "No Multica agents are visible to this token."
            elif not shown:
                reply = f"No Multica agent name contains '{arg}'. Available: {_names_hint(agents)}"
            else:
                yield _choices_update(ctx.run_id, shown)
                lines = [f"Multica agents matching '{arg}':" if arg else "Multica agents:"]
                for index, agent in enumerate(shown, start=1):
                    mark = " (current)" if str(agent.get("id")) == current_id else ""
                    lines.append(f"{index}) {agent.get('name') or '(unnamed)'} [{short_id(agent.get('id'))}]{mark}")
                if config["allow_agent_switch"]:
                    lines.append(f"Switch with: {prefix} use <number or name>")
                reply = "\n".join(lines)

        elif verb == "use":
            if not config["allow_agent_switch"]:
                reply = "Switching agents is disabled for this runner."
            elif not arg:
                reply = f"Usage: {prefix} use <number, name or id>"
            else:
                agent: dict[str, typing.Any] | None = None
                reply = ""
                if arg.isdigit():
                    agent = _pick_choice(state, int(arg))
                    if agent is None:
                        reply = (
                            f"序号 {arg} 无效或已过期（{CHOICES_TTL // 60} 分钟内有效）。"
                            f"先发送 '{prefix} agents' 或 '{prefix} find <关键词>' 查看带序号的列表。"
                        )
                else:
                    try:
                        agent = await client.resolve_agent(arg)
                    except AgentResolutionError as e:
                        if e.candidates:
                            yield _choices_update(ctx.run_id, e.candidates)
                            reply = f"{e.message}用 {prefix} use <序号> 或完整 ID 选择。"
                        else:
                            reply = f"{e.message}。发送 '{prefix} agents' 查看全部。"
                if agent is not None:
                    agent_id = str(agent["id"])
                    agent_name = str(agent.get("name") or "")
                    yield RunnerResult.state_updated(ctx.run_id, STATE_AGENT, agent_id, scope="conversation")
                    yield RunnerResult.state_updated(ctx.run_id, STATE_AGENT_NAME, agent_name, scope="conversation")
                    reply = f"Now chatting with Multica agent {agent_name or agent_id}."
                    if agent_id != current_id:
                        reply += " A new Multica chat session will start with your next message."

        elif verb in ("new", "reset"):
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION, "", scope="conversation")
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION_AGENT, "", scope="conversation")
            reply = "Started over: your next message opens a new Multica chat session."

        else:
            session = state.get(STATE_SESSION) if current_id and state.get(STATE_SESSION_AGENT) == current_id else ""
            if current_id:
                agent_label = f"{current_name} [{short_id(current_id)}]" if current_name else current_id
            else:
                agent_label = config["agent"] or "(none)"
            lines = [
                f"Current Multica agent: {agent_label}",
                f"Chat session: {session or '(new on next message)'}",
                f"Progress mode: {config['progress_mode']}",
                "Commands:",
                f"  {prefix} agents [keyword] - list agents, optionally filtered by name",
                f"  {prefix} find <keyword> - same as agents <keyword>",
            ]
            if config["allow_agent_switch"]:
                lines.append(f"  {prefix} use <number, name or id> - switch agent")
            lines.append(f"  {prefix} new - start a new chat session")
            reply = "\n".join(lines)

        yield RunnerResult.message_completed(ctx.run_id, Message(role="assistant", content=reply))


class _Progress:
    """Turn task lifecycle lines into results for the chosen progress mode.

    ``messages`` sends each line as its own completed message and the answer as the
    last one, unprefixed. ``stream`` appends every line, then the answer, to one
    streamed message. ``off`` sends only the answer, as 0.1.x did.
    """

    def __init__(self, run_id: str, mode: str, interval: float):
        self.run_id = run_id
        self.mode = mode
        self.interval = interval
        self.text = ""
        self.last_emit: float | None = None

    def due(self, now: float) -> bool:
        return self.mode != "off" and (self.last_emit is None or now - self.last_emit >= self.interval)

    def emit(self, line: str) -> list[RunnerResult]:
        if self.mode == "off":
            return []
        self.last_emit = _monotonic()
        if self.mode == "messages":
            return [RunnerResult.message_completed(self.run_id, Message(role="assistant", content=line))]
        return [self._delta(f"{line}\n", final=False)]

    def close(self, line: str) -> list[RunnerResult]:
        """Final progress line before a failure."""
        if self.mode == "stream":
            return [self._delta(f"{line}\n", final=True)]
        return self.emit(line)

    def answer(self, content: str) -> list[RunnerResult]:
        if self.mode == "stream":
            return [self._delta(f"\n{content}" if self.text else content, final=True)]
        return [RunnerResult.message_completed(self.run_id, Message(role="assistant", content=content))]

    def _delta(self, piece: str, *, final: bool) -> RunnerResult:
        self.text += piece
        chunk = MessageChunk(role="assistant", content=piece, all_content=self.text, is_final=final)
        return RunnerResult.message_delta(self.run_id, chunk)


# ----------------------------------------------------------------- helpers


def _number(value: typing.Any, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise MulticaConfigError(f"{name} must be a number") from None
    if not low <= number <= high:
        raise MulticaConfigError(f"{name} must be between {low} and {high}")
    return number


def _parse_command(text: str, prefix: str) -> tuple[str, str] | None:
    if not prefix or not text.startswith(prefix):
        return None
    rest = text[len(prefix) :]
    if rest and not rest[0].isspace():
        return None  # e.g. "/multicaX" is ordinary text
    parts = rest.strip().split(maxsplit=1)
    verb = parts[0].lower() if parts else "help"
    arg = parts[1].strip() if len(parts) > 1 else ""
    return verb, arg


def _known_agent(config: dict[str, typing.Any], state: dict[str, typing.Any]) -> tuple[str, str]:
    """Current agent id and name known without a request (empty id if a name is still unresolved)."""
    if state.get(STATE_AGENT):
        return str(state[STATE_AGENT]), str(state.get(STATE_AGENT_NAME) or "")
    cached = state.get(STATE_RESOLVED)
    if isinstance(cached, dict) and cached.get("query") == config["agent"] and cached.get("id"):
        return str(cached["id"]), str(cached.get("name") or "")
    if not config["agent"]:
        return config["legacy_agent_id"], ""
    if is_uuid(config["agent"]):
        return config["agent"], ""
    return "", ""


def _choices_update(run_id: str, agents: list[dict[str, typing.Any]]) -> RunnerResult:
    items = [{"id": str(a.get("id")), "name": str(a.get("name") or "")} for a in agents]
    value = {"items": items, "expires_at": _now() + CHOICES_TTL}
    return RunnerResult.state_updated(run_id, STATE_CHOICES, value, scope="conversation")


def _pick_choice(state: dict[str, typing.Any], number: int) -> dict[str, typing.Any] | None:
    choices = state.get(STATE_CHOICES)
    if not isinstance(choices, dict):
        return None
    items = choices.get("items")
    try:
        expires_at = float(choices.get("expires_at") or 0)
    except (TypeError, ValueError):
        return None
    if expires_at < _now() or not isinstance(items, list) or not 1 <= number <= len(items):
        return None
    item = items[number - 1]
    return item if isinstance(item, dict) and item.get("id") else None


def _names_hint(agents: list[dict[str, typing.Any]]) -> str:
    names = ", ".join(str(a.get("name") or "(unnamed)") for a in agents[:MAX_LISTED_NAMES])
    return names + (", …" if len(agents) > MAX_LISTED_NAMES else "")


def _failure_line(code: str) -> str:
    if code == "multica.timeout":
        return "⚠️ 超时，任务仍在 Multica 里跑"
    if code == "multica.no_reply":
        return "⚠️ 任务已结束但没有回复（可能被取消）"
    return f"⚠️ 等待回复时出错（{code}）"


def _find_reply(messages: list[dict[str, typing.Any]], task_id: str) -> dict[str, typing.Any] | None:
    for message in reversed(messages):
        if message.get("role") == "assistant" and str(message.get("task_id") or "") == task_id:
            return message
    return None


def _session_title(ctx: RunnerContext) -> str:
    conversation = getattr(ctx, "conversation", None)
    conversation_id = getattr(conversation, "conversation_id", None) if conversation else None
    return f"LangBot · {conversation_id}"[:120] if conversation_id else "LangBot chat"
