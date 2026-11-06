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
from pkg.i18n import DEFAULT_LANGUAGE, get_text, normalize_language
from pkg.multica_client import (
    TASK_RUNNING,
    AgentResolutionError,
    AsyncMulticaClient,
    is_uuid,
    match_agents,
    names_hint,
    numbered,
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

    def _language(self) -> str:
        """Plugin-level ``language`` of this invocation (installation config, not runner config)."""
        plugin = getattr(self, "plugin", None)
        if callable(getattr(plugin, "get_language", None)):
            return normalize_language(plugin.get_language())
        try:
            # Not running under MulticaAgentPlugin (e.g. NonePlugin in tests): read the
            # installation config bound to this invocation directly.
            config = self.get_plugin_config()
        except Exception:
            config = {}
        return normalize_language(config.get("language") or DEFAULT_LANGUAGE)

    def _validate_config(self, ctx: RunnerContext, lang: str) -> dict[str, typing.Any]:
        config = ctx.config or {}

        server_url = str(config.get("server-url") or DEFAULT_SERVER_URL).strip()
        try:
            endpoint(server_url)
        except ValueError as exc:
            raise MulticaConfigError(get_text(lang, "config.server_url_invalid", detail=exc)) from None

        token = str(config.get("api-token") or "").strip()
        if not token:
            raise MulticaConfigError(get_text(lang, "config.api_token_required"))

        workspace_id = str(config.get("workspace-id") or "").strip()
        if not workspace_id:
            raise MulticaConfigError(get_text(lang, "config.workspace_id_required"))

        timeout = _number(lang, config.get("timeout", 600), "timeout", 10, 3600)
        poll_interval = _number(lang, config.get("poll-interval", 2), "poll-interval", 0.5, 60)
        request_timeout = _number(lang, config.get("request-timeout", 30), "request-timeout", 1, 300)

        prefix = str(config.get("command-prefix") or "/multica").strip()

        progress_mode = str(config.get("progress-mode") or "messages").strip().lower()
        if progress_mode not in PROGRESS_MODES:
            raise MulticaConfigError(get_text(lang, "config.progress_mode_invalid", options=", ".join(PROGRESS_MODES)))
        progress_interval = _number(lang, config.get("progress-interval", 15), "progress-interval", 5, 300)

        return {
            "language": lang,
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
        lang = self._language()
        try:
            config = self._validate_config(ctx, lang)
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
                yield RunnerResult.run_failed(
                    ctx.run_id, error=get_text(lang, "error.empty_input"), code="multica.empty_input"
                )
                return

            try:
                agent_id, agent_name, updates = await self._select_agent(ctx.run_id, client, config, state)
            except AgentResolutionError as e:
                if e.candidates:
                    yield _choices_update(ctx.run_id, e.candidates)
                    hint = (
                        "error.ambiguous_hint_switch" if config["allow_agent_switch"] else "error.ambiguous_hint_config"
                    )
                    error = get_text(
                        lang,
                        "error.agent_ambiguous",
                        query=e.query,
                        candidates=numbered(e.candidates, get_text(lang, "agents.unnamed")),
                        hint=get_text(lang, hint, prefix=config["command_prefix"]),
                    )
                else:
                    error = get_text(lang, "error.agent_not_resolved", query=e.query, names=_names(lang, e.visible))
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
            for result in progress.emit(get_text(lang, "progress.submitted", agent=label, task_id=short_id(task_id))):
                yield result

            reply: dict[str, typing.Any] = {}
            try:
                async for item in self._wait_for_reply(ctx, client, config, session_id, task_id, progress, label):
                    if isinstance(item, RunnerResult):
                        yield item
                    else:
                        reply = item
            except MulticaAPIError as e:
                for result in progress.close(_failure_line(lang, e.code)):
                    yield result
                raise

            if reply.get("failure_reason"):
                for result in progress.close(get_text(lang, "progress.failed", agent=label)):
                    yield result
                # The Multica failure text is server output: appended verbatim, never translated.
                yield RunnerResult.run_failed(
                    ctx.run_id,
                    error=get_text(lang, "error.agent_failed", detail=reply.get("content") or reply["failure_reason"]),
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
                error=get_text(lang, "error.unexpected", name=e.__class__.__name__),
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
                get_text(config["language"], "error.no_agent_selected", prefix=config["command_prefix"])
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
        lang = config["language"]
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
                    get_text(lang, "error.task_no_reply"),
                    code="multica.no_reply",
                )

            now = _monotonic()
            if status == TASK_RUNNING and not running:
                running = True
                for result in progress.emit(get_text(lang, "progress.started", agent=label)):
                    yield result
            elif progress.due(now):
                waited = int(now - started_at)
                key = "progress.running" if running else "progress.queued"
                for result in progress.emit(get_text(lang, key, seconds=waited)):
                    yield result

            if _monotonic() >= deadline:
                raise MulticaAPIError(
                    get_text(lang, "error.timeout", seconds=int(timeout)),
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
        lang = config["language"]
        prefix = config["command_prefix"]
        unnamed = get_text(lang, "agents.unnamed")
        current_id, current_name = _known_agent(config, state)

        if verb == "find" and not arg:
            reply = get_text(lang, "find.usage", prefix=prefix)

        elif verb in ("agents", "find"):
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
                reply = get_text(lang, "agents.empty")
            elif not shown:
                reply = get_text(lang, "find.no_match", keyword=arg, names=_names(lang, agents))
            else:
                yield _choices_update(ctx.run_id, shown)
                header = (
                    get_text(lang, "agents.header_filtered", keyword=arg) if arg else get_text(lang, "agents.header")
                )
                lines = [header]
                for index, agent in enumerate(shown, start=1):
                    mark = get_text(lang, "agents.current_mark") if str(agent.get("id")) == current_id else ""
                    lines.append(f"{index}) {agent.get('name') or unnamed} [{short_id(agent.get('id'))}]{mark}")
                if config["allow_agent_switch"]:
                    lines.append(get_text(lang, "agents.switch_hint", prefix=prefix))
                reply = "\n".join(lines)

        elif verb == "use":
            if not config["allow_agent_switch"]:
                reply = get_text(lang, "use.disabled")
            elif not arg:
                reply = get_text(lang, "use.usage", prefix=prefix)
            else:
                agent: dict[str, typing.Any] | None = None
                reply = ""
                if arg.isdigit():
                    agent = _pick_choice(state, int(arg))
                    if agent is None:
                        reply = get_text(lang, "use.bad_number", number=arg, minutes=CHOICES_TTL // 60, prefix=prefix)
                else:
                    try:
                        agent = await client.resolve_agent(arg)
                    except AgentResolutionError as e:
                        if e.candidates:
                            yield _choices_update(ctx.run_id, e.candidates)
                            candidates = numbered(e.candidates, unnamed)
                            reply = get_text(lang, "use.ambiguous", query=arg, candidates=candidates, prefix=prefix)
                        else:
                            reply = get_text(
                                lang, "use.no_match", query=arg, names=_names(lang, e.visible), prefix=prefix
                            )
                if agent is not None:
                    agent_id = str(agent["id"])
                    agent_name = str(agent.get("name") or "")
                    yield RunnerResult.state_updated(ctx.run_id, STATE_AGENT, agent_id, scope="conversation")
                    yield RunnerResult.state_updated(ctx.run_id, STATE_AGENT_NAME, agent_name, scope="conversation")
                    key = "use.ok" if agent_id == current_id else "use.ok_new_session"
                    reply = get_text(lang, key, agent=agent_name or agent_id)

        elif verb in ("new", "reset"):
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION, "", scope="conversation")
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION_AGENT, "", scope="conversation")
            reply = get_text(lang, "new.ok")

        else:
            session = state.get(STATE_SESSION) if current_id and state.get(STATE_SESSION_AGENT) == current_id else ""
            if current_id:
                agent_label = f"{current_name} [{short_id(current_id)}]" if current_name else current_id
            else:
                agent_label = config["agent"] or get_text(lang, "help.none")
            lines = [
                get_text(lang, "help.agent", agent=agent_label),
                get_text(lang, "help.session", session=session or get_text(lang, "help.session_new")),
                get_text(lang, "help.progress", mode=config["progress_mode"]),
                get_text(lang, "help.language", language=lang),
                get_text(lang, "help.commands"),
                get_text(lang, "help.cmd_agents", prefix=prefix),
                get_text(lang, "help.cmd_find", prefix=prefix),
            ]
            if config["allow_agent_switch"]:
                lines.append(get_text(lang, "help.cmd_use", prefix=prefix))
            lines.append(get_text(lang, "help.cmd_new", prefix=prefix))
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


def _number(lang: str, value: typing.Any, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise MulticaConfigError(get_text(lang, "config.not_number", name=name)) from None
    if not low <= number <= high:
        raise MulticaConfigError(get_text(lang, "config.out_of_range", name=name, low=low, high=high))
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


def _names(lang: str, agents: list[dict[str, typing.Any]]) -> str:
    return names_hint(agents, get_text(lang, "agents.unnamed")) or get_text(lang, "help.none")


def _failure_line(lang: str, code: str) -> str:
    if code == "multica.timeout":
        return get_text(lang, "progress.timeout")
    if code == "multica.no_reply":
        return get_text(lang, "progress.no_reply")
    return get_text(lang, "progress.error", code=code)


def _find_reply(messages: list[dict[str, typing.Any]], task_id: str) -> dict[str, typing.Any] | None:
    for message in reversed(messages):
        if message.get("role") == "assistant" and str(message.get("task_id") or "") == task_id:
            return message
    return None


def _session_title(ctx: RunnerContext) -> str:
    conversation = getattr(ctx, "conversation", None)
    conversation_id = getattr(conversation, "conversation_id", None) if conversation else None
    return f"LangBot · {conversation_id}"[:120] if conversation_id else "LangBot chat"
