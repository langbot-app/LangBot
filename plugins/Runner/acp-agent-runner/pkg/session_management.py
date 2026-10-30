"""Shared session-management helpers for ACP commands and runners."""

from __future__ import annotations

import contextlib
import hashlib
import json
import typing

from pkg.daemon_relay import (
    agent_runtime_daemon_config_from_plugin_config,
    get_agent_runtime_daemon_hub,
)

STORAGE_PREFIX = "acp-session:v1"


def conversation_id_from_command(context: typing.Any) -> str:
    """Build the Host conversation id used by IM-backed Runner state."""

    launcher_type = getattr(getattr(context, "session", None), "launcher_type", None)
    launcher_type = getattr(launcher_type, "value", launcher_type)
    launcher_id = getattr(getattr(context, "session", None), "launcher_id", None)
    if not launcher_type or launcher_id in (None, ""):
        raise ValueError("command session has no conversation identity")
    return f"{launcher_type}_{launcher_id}"


def storage_key(kind: str, conversation_id: str) -> str:
    digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
    return f"{STORAGE_PREFIX}:{kind}:{digest}"


async def read_json(plugin: typing.Any, key: str, default: typing.Any = None) -> typing.Any:
    try:
        raw = await plugin.get_plugin_storage(key)
    except Exception:
        return default
    if not raw:
        return default
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return default


async def write_json(plugin: typing.Any, key: str, value: typing.Any) -> None:
    await plugin.set_plugin_storage(
        key,
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
    )


async def delete_value(plugin: typing.Any, key: str) -> None:
    try:
        await plugin.delete_plugin_storage(key)
    except Exception:
        # Older runtimes can return a missing-key error. Deletion is idempotent.
        return


def normalize_sessions(result: typing.Any) -> list[dict[str, str]]:
    """Return a bounded, newest-first list from an ACP session/list result."""

    if isinstance(result, dict):
        raw_sessions = result.get("sessions")
    else:
        raw_sessions = None
    if not isinstance(raw_sessions, list):
        return []

    sessions: list[dict[str, str]] = []
    for item in raw_sessions:
        if not isinstance(item, dict):
            continue
        session_id = str(item.get("sessionId") or item.get("session_id") or item.get("id") or "").strip()
        if not session_id:
            continue
        sessions.append(
            {
                "session_id": session_id,
                "title": str(item.get("title") or "未命名会话").strip() or "未命名会话",
                "cwd": str(item.get("cwd") or item.get("directory") or "").strip(),
                "updated_at": str(item.get("updatedAt") or item.get("updated_at") or "").strip(),
            }
        )
    sessions.sort(key=lambda item: item["updated_at"], reverse=True)
    return sessions[:100]


def resolve_session_target(reference: str, sessions: list[dict[str, str]]) -> str | None:
    reference = str(reference or "").strip()
    if not reference:
        return None
    if reference.isdigit():
        index = int(reference) - 1
        if 0 <= index < len(sessions):
            return sessions[index]["session_id"]
        return None
    for item in sessions:
        if item["session_id"] == reference:
            return reference
    return None


async def run_daemon_control(
    plugin: typing.Any,
    control: dict[str, typing.Any],
    operation: str,
    **arguments: typing.Any,
) -> typing.Any:
    """Run one non-prompt ACP control operation through the configured daemon."""

    daemon_config = agent_runtime_daemon_config_from_plugin_config(
        plugin.get_config(),
        env_prefix="LANGBOT_ACP_DAEMON",
    )
    hub = get_agent_runtime_daemon_hub("acp", error_code_prefix="acp")
    await hub.start(
        host=daemon_config["host"],
        port=daemon_config["port"],
        token=daemon_config["token"],
    )
    daemon_id = str(control.get("daemon_id") or "").strip()
    if not daemon_id:
        raise RuntimeError("ACP daemon id is unavailable; send one normal message first")
    timeout = float(control.get("timeout") or 60.0)
    await hub.wait_for_daemon(daemon_id, min(timeout, 60.0))
    payload = {
        "operation": operation,
        "arguments": arguments,
        "config": dict(control),
    }
    result: typing.Any = None
    received_result = False
    async with contextlib.aclosing(
        hub.run_job(
            daemon_id=daemon_id,
            payload=payload,
            tools=None,
            timeout=timeout,
        )
    ) as events:
        async for event in events:
            if event.get("type") == "control.result":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                result = data.get("result")
                received_result = True
            elif event.get("type") == "run.failed":
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                raise RuntimeError(str(data.get("error") or data.get("code") or "ACP control operation failed"))
    if not received_result:
        raise RuntimeError(f"ACP daemon returned no result for {operation}")
    return result
