"""Multica Agent runner: chat with a Multica agent from LangBot.

Each LangBot conversation is mapped to one Multica chat session. A user
message is posted to that session, which enqueues a task for the selected
Multica agent; the runner polls until the agent's reply for that task is
written back and returns it as the LangBot reply.

Conversation-scoped state:
- multica.agent_id: agent chosen in chat with ``<prefix> use``; overrides config.
- multica.session_id: Multica chat session bound to this conversation.
- multica.session_agent_id: agent the stored session was created for.
"""

from __future__ import annotations

import asyncio
import logging
import time
import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner import RunnerContext, RunnerResult
from pkg.endpoint import endpoint
from pkg.errors import MulticaAPIError, MulticaConfigError
from pkg.multica_client import AsyncMulticaClient

logger = logging.getLogger(__name__)

DEFAULT_SERVER_URL = "https://api.multica.ai"
STATE_AGENT = "multica.agent_id"
STATE_SESSION = "multica.session_id"
STATE_SESSION_AGENT = "multica.session_agent_id"

# Indirection so tests can run the polling loop without real delays.
_sleep = asyncio.sleep
_monotonic = time.monotonic


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

        return {
            "server_url": server_url,
            "token": token,
            "workspace_id": workspace_id,
            "agent_id": str(config.get("agent-id") or "").strip(),
            "allow_agent_switch": bool(config.get("allow-agent-switch", True)),
            "command_prefix": prefix,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "request_timeout": request_timeout,
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

            agent_id = str(state.get(STATE_AGENT) or config["agent_id"])
            if not agent_id:
                raise MulticaConfigError(
                    f"No Multica agent selected. Set agent-id in the runner config or send "
                    f"'{config['command_prefix']} use <agent>'."
                )

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

            reply = await self._wait_for_reply(ctx, client, config, session_id, task_id)
            if reply.get("failure_reason"):
                yield RunnerResult.run_failed(
                    ctx.run_id,
                    error=f"Multica agent run failed: {reply.get('content') or reply['failure_reason']}",
                    code="multica.agent_failed",
                )
                return

            yield RunnerResult.message_completed(
                ctx.run_id,
                Message(role="assistant", content=str(reply.get("content") or "")),
            )
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

    async def _wait_for_reply(
        self,
        ctx: RunnerContext,
        client: AsyncMulticaClient,
        config: dict[str, typing.Any],
        session_id: str,
        task_id: str,
    ) -> dict[str, typing.Any]:
        timeout = config["timeout"]
        host_deadline = getattr(ctx.runtime, "deadline_at", None) if ctx.runtime else None
        if host_deadline:
            # Leave a small margin so the failure is reported before the host cuts the run.
            timeout = max(1.0, min(timeout, float(host_deadline) - time.time() - 2))
        deadline = _monotonic() + timeout

        while True:
            await _sleep(config["poll_interval"])
            reply = _find_reply(await client.recent_messages(session_id), task_id)
            if reply is not None:
                return reply

            if task_id not in await client.pending_task_ids(session_id):
                # The task left the queue; its reply row may have landed between the reads.
                reply = _find_reply(await client.recent_messages(session_id), task_id)
                if reply is not None:
                    return reply
                raise MulticaAPIError(
                    "The Multica agent task ended without a reply (it may have been cancelled).",
                    code="multica.no_reply",
                )

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
        current = str(state.get(STATE_AGENT) or config["agent_id"])

        if verb == "agents":
            agents = await client.list_agents()
            if not agents:
                reply = "No Multica agents are visible to this token."
            else:
                lines = ["Multica agents:"]
                for agent in agents:
                    mark = " (current)" if str(agent.get("id")) == current else ""
                    lines.append(f"- {agent.get('name') or '(unnamed)'} [{agent.get('id')}]{mark}")
                if config["allow_agent_switch"]:
                    lines.append(f"Switch with: {prefix} use <name or id>")
                reply = "\n".join(lines)

        elif verb == "use":
            if not config["allow_agent_switch"]:
                reply = "Switching agents is disabled for this runner."
            elif not arg:
                reply = f"Usage: {prefix} use <name or id>"
            else:
                agents = await client.list_agents()
                matches = _match_agents(agents, arg)
                if len(matches) == 1:
                    agent = matches[0]
                    agent_id = str(agent.get("id"))
                    yield RunnerResult.state_updated(ctx.run_id, STATE_AGENT, agent_id, scope="conversation")
                    reply = f"Now chatting with Multica agent {agent.get('name') or agent_id}."
                    if agent_id != current:
                        reply += " A new Multica chat session will start with your next message."
                elif not matches:
                    reply = f"No Multica agent matches '{arg}'. Send '{prefix} agents' to list them."
                else:
                    names = ", ".join(f"{a.get('name')} [{a.get('id')}]" for a in matches[:10])
                    reply = f"'{arg}' matches several agents: {names}. Use the agent id."

        elif verb in ("new", "reset"):
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION, "", scope="conversation")
            yield RunnerResult.state_updated(ctx.run_id, STATE_SESSION_AGENT, "", scope="conversation")
            reply = "Started over: your next message opens a new Multica chat session."

        else:
            session = state.get(STATE_SESSION) if state.get(STATE_SESSION_AGENT) == current else ""
            lines = [
                f"Current Multica agent: {current or '(none)'}",
                f"Chat session: {session or '(new on next message)'}",
                "Commands:",
                f"  {prefix} agents - list agents",
            ]
            if config["allow_agent_switch"]:
                lines.append(f"  {prefix} use <name or id> - switch agent")
            lines.append(f"  {prefix} new - start a new chat session")
            reply = "\n".join(lines)

        yield RunnerResult.message_completed(ctx.run_id, Message(role="assistant", content=reply))


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


def _match_agents(agents: list[dict[str, typing.Any]], query: str) -> list[dict[str, typing.Any]]:
    by_id = [a for a in agents if str(a.get("id")) == query]
    if by_id:
        return by_id
    lowered = query.casefold()
    exact = [a for a in agents if str(a.get("name") or "").casefold() == lowered]
    if exact:
        return exact
    return [a for a in agents if lowered in str(a.get("name") or "").casefold()]


def _find_reply(messages: list[dict[str, typing.Any]], task_id: str) -> dict[str, typing.Any] | None:
    for message in reversed(messages):
        if message.get("role") == "assistant" and str(message.get("task_id") or "") == task_id:
            return message
    return None


def _session_title(ctx: RunnerContext) -> str:
    conversation = getattr(ctx, "conversation", None)
    conversation_id = getattr(conversation, "conversation_id", None) if conversation else None
    return f"LangBot · {conversation_id}"[:120] if conversation_id else "LangBot chat"
