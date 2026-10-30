"""User-side daemon for ACP Runner.

The daemon connects outward to the ACP runner plugin. It is useful when the
LangBot server cannot SSH into the user's workstation. The local ACP process
talks to a localhost MCP server; that server forwards LangBot asset requests
over the already-established WebSocket connection.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import shlex
import time
import typing

from pkg.acp_client import AcpError, AcpStdioClient
from pkg.daemon_relay import AgentRuntimeDaemonClient, LocalMCPProxy
from pkg.prompt import acp_prompt_blocks, has_acp_prompt_input, prompt_capabilities
from pkg.session import CLAUDE_ENV_VARS_TO_UNSET, build_session_params

logger = logging.getLogger("langbot-acp-daemon")


def _parse_args(value: typing.Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return shlex.split(text)


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


def _result_event(
    result_type: str, data: dict[str, typing.Any], *, sequence: int | None = None
) -> dict[str, typing.Any]:
    event = {"type": result_type, "data": data}
    if sequence is not None:
        event["sequence"] = sequence
    return event


class RunnerDaemon(AgentRuntimeDaemonClient):
    """Outbound WebSocket daemon that runs ACP jobs locally."""

    async def run_job(self, job_id: str, payload: dict[str, typing.Any]) -> None:
        proxy: LocalMCPProxy | None = None
        client: AcpStdioClient | None = None
        try:
            config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
            prompt_text = str(payload.get("prompt_text") or "")
            input_data = payload.get("input") if isinstance(payload.get("input"), dict) else {}
            if not has_acp_prompt_input(prompt_text, input_data):
                raise AcpError("prompt_text is required", code="acp.daemon_empty_prompt")

            command_args = _parse_args(config.get("acp_command"))
            if not command_args:
                raise AcpError("acp_command is required", code="acp.daemon_config_invalid")

            mcp_servers = list(config.get("mcp_servers") or [])
            if config.get("langbot_assets_enabled", True):
                proxy = self.create_mcp_proxy(job_id, request_timeout=float(config.get("mcp_request_timeout") or 60.0))
                proxy.start()
                mcp_servers.append(proxy.server_config())

            client = AcpStdioClient(
                command=command_args[0],
                args=command_args[1:],
                cwd=str(config.get("cwd") or config.get("workspace") or os.getcwd()),
                env={str(k): str(v) for k, v in dict(config.get("env") or {}).items()},
                unset_env=(
                    CLAUDE_ENV_VARS_TO_UNSET if str(config.get("provider") or "custom") == "claude-code" else ()
                ),
                permission_decision=str(config.get("permission_decision") or "allow_once"),
                startup_timeout=float(config.get("startup_timeout") or 30.0),
            )

            async with client:
                initialize_result = await client.initialize(timeout=float(config.get("initialize_timeout") or 30.0))
                session_id, created = await self._create_or_resume_session(
                    client, initialize_result, config, mcp_servers
                )
                stored_session_id = str(config.get("stored_session_id") or "")
                if created or stored_session_id != session_id:
                    await self.emit_event(
                        job_id,
                        _result_event(
                            "state.updated",
                            {
                                "key": "external.acp_session_id",
                                "value": session_id,
                                "scope": "conversation",
                            },
                        ),
                    )
                prompt_blocks = acp_prompt_blocks(prompt_text, input_data, prompt_capabilities(initialize_result))
                await self._stream_prompt_results(client, job_id, session_id, prompt_blocks, config)
        except asyncio.CancelledError:
            await self.emit_event(
                job_id,
                _result_event(
                    "run.failed",
                    {"error": "ACP daemon run cancelled", "code": "acp.daemon_cancelled", "retryable": True},
                ),
            )
            return
        except TimeoutError:
            await self.emit_event(
                job_id,
                _result_event(
                    "run.failed",
                    {"error": "ACP daemon run timed out", "code": "acp.daemon_timeout", "retryable": True},
                ),
            )
        except AcpError as exc:
            await self.emit_event(
                job_id,
                _result_event("run.failed", {"error": exc.message, "code": exc.code, "retryable": exc.retryable}),
            )
        except Exception as exc:
            logger.exception("ACP daemon job failed: %s", exc)
            await self.emit_event(
                job_id,
                _result_event("run.failed", {"error": str(exc), "code": "acp.daemon_unexpected"}),
            )
        finally:
            if client and client.stderr_tail.strip():
                logger.debug("ACP stderr tail for %s: %s", job_id, client.stderr_tail.strip())
            if proxy is not None:
                proxy.stop()

    async def _create_or_resume_session(
        self,
        client: AcpStdioClient,
        initialize_result: dict[str, typing.Any],
        config: dict[str, typing.Any],
        mcp_servers: list[dict[str, typing.Any]],
    ) -> tuple[str, bool]:
        capabilities = initialize_result.get("agentCapabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}

        stored_session_id = str(config.get("stored_session_id") or "").strip()
        timeout = float(config.get("timeout") or 300.0)
        cwd = str(config.get("session_cwd") or config.get("workspace") or os.getcwd())
        if stored_session_id and config.get("reuse_session", True):
            if _runtime_has_method(capabilities, "session/resume"):
                result = await client.request(
                    "session/resume",
                    build_session_params(
                        provider=str(config.get("provider") or "custom"),
                        session_id=stored_session_id,
                        cwd=cwd,
                        mcp_servers=mcp_servers,
                    ),
                    timeout=timeout,
                )
                return _extract_session_id(result) or stored_session_id, False
            if _runtime_has_method(capabilities, "session/load"):
                result = await client.request(
                    "session/load",
                    build_session_params(
                        provider=str(config.get("provider") or "custom"),
                        session_id=stored_session_id,
                        cwd=cwd,
                        mcp_servers=mcp_servers,
                    ),
                    timeout=timeout,
                )
                await client.drain_updates()
                return _extract_session_id(result) or stored_session_id, False

        if not config.get("create_session_if_missing", True):
            raise AcpError(
                "no stored ACP session and create-session-if-missing is disabled", code="acp.session_missing"
            )

        result = await client.request(
            "session/new",
            build_session_params(
                provider=str(config.get("provider") or "custom"),
                cwd=cwd,
                mcp_servers=mcp_servers,
            ),
            timeout=timeout,
        )
        session_id = _extract_session_id(result)
        if not session_id:
            raise AcpError(f"ACP session/new did not return a session id: {result!r}", code="acp.response_invalid")
        return session_id, True

    async def _stream_prompt_results(
        self,
        client: AcpStdioClient,
        job_id: str,
        session_id: str,
        prompt_blocks: list[dict[str, typing.Any]],
        config: dict[str, typing.Any],
    ) -> None:
        prompt_request = client.send_request(
            "session/prompt",
            {"sessionId": session_id, "prompt": prompt_blocks},
        )
        sequence = 0
        final_text_parts: list[str] = []
        active_message_id = ""
        active_tool_calls: dict[str, str] = {}
        timeout = float(config.get("timeout") or 300.0)
        deadline = time.monotonic() + timeout
        streaming = bool(config.get("streaming", True))

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
                    await self.emit_event(
                        job_id,
                        _result_event(
                            "message.delta",
                            {
                                "chunk": {
                                    "role": "assistant",
                                    "content": text,
                                    "all_content": "".join(final_text_parts),
                                    "msg_sequence": sequence,
                                }
                            },
                            sequence=sequence,
                        ),
                    )

            tool_payload = _tool_update_payload(update)
            if tool_payload:
                await self._emit_tool_update(job_id, tool_payload, active_tool_calls)

        await prompt_request.wait(timeout=timeout)
        final_text = "".join(final_text_parts).strip()
        if not final_text:
            await self.emit_event(
                job_id,
                _result_event(
                    "run.failed", {"error": "ACP agent returned no assistant text", "code": "acp.empty_response"}
                ),
            )
            return

        await self.emit_event(
            job_id,
            _result_event("message.completed", {"message": {"role": "assistant", "content": final_text}}),
        )
        await self.emit_event(job_id, _result_event("run.completed", {"finish_reason": "stop"}))

    async def _emit_tool_update(
        self,
        job_id: str,
        tool_payload: dict[str, typing.Any],
        active_tool_calls: dict[str, str],
    ) -> None:
        tool_call_id = str(tool_payload.get("toolCallId") or tool_payload.get("id") or "")
        observed_tool_name = _tool_update_name(tool_payload)
        status = str(tool_payload.get("status") or "")
        if tool_call_id and tool_call_id not in active_tool_calls:
            active_tool_calls[tool_call_id] = observed_tool_name
            tool_name = observed_tool_name
            await self.emit_event(
                job_id,
                _result_event(
                    "tool.call.started",
                    {"tool_call_id": tool_call_id, "tool_name": tool_name, "parameters": {}},
                ),
            )
        if tool_call_id and status in {"completed", "failed", "cancelled"}:
            tool_name = active_tool_calls.get(tool_call_id, observed_tool_name)
            await self.emit_event(
                job_id,
                _result_event(
                    "tool.call.completed",
                    {
                        "tool_call_id": tool_call_id,
                        "tool_name": tool_name,
                        "result": tool_payload if status == "completed" else None,
                        "error": None if status == "completed" else json.dumps(tool_payload, ensure_ascii=False),
                    },
                ),
            )


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect a local ACP runtime to LangBot ACP Runner.")
    parser.add_argument("--url", required=True, help="Daemon hub WebSocket URL, for example ws://host:8766")
    parser.add_argument("--daemon-id", required=True, help="Stable daemon id configured in the LangBot runner.")
    parser.add_argument("--token", default=os.environ.get("LANGBOT_ACP_DAEMON_TOKEN", ""), help="Shared hub token.")
    parser.add_argument("--reconnect-delay", type=float, default=5.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_cli_args()
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    daemon = RunnerDaemon(
        url=args.url,
        daemon_id=args.daemon_id,
        token=args.token,
        reconnect_delay=args.reconnect_delay,
    )
    await daemon.run_forever()


def main() -> int:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(async_main())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
