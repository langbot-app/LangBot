"""Live latest n8n regression for the LangBot n8n Agent Runner."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

from langbot_plugin.api.entities.builtin.runner import (
    ActorContext,
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    ConversationContext,
    DeliveryContext,
    RunnerContext,
)

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "n8n-agent"
SENTINEL = "LANGBOT_N8N_DAILY_OK"


def _load_runner():
    saved = {key: value for key, value in sys.modules.items() if key == "pkg" or key.startswith("pkg.")}
    for key in saved:
        del sys.modules[key]
    sys.path.insert(0, str(PLUGIN))
    try:
        spec = importlib.util.spec_from_file_location("live_n8n_agent_runner", PLUGIN / "components/runner/default.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load n8n Agent Runner")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, saved
    except Exception:
        sys.path.remove(str(PLUGIN))
        for key in list(sys.modules):
            if key == "pkg" or key.startswith("pkg."):
                del sys.modules[key]
        sys.modules.update(saved)
        raise


def _context(state: dict[str, str] | None = None) -> RunnerContext:
    return RunnerContext(
        run_id="n8n-latest-daily-regression",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="n8n-latest-daily-regression",
            event_type="message.received",
            source="ci",
        ),
        conversation=ConversationContext(conversation_id="daily-regression", session_id="daily-regression"),
        input=AgentInput(text=f"Reply with exactly {SENTINEL}."),
        delivery=DeliveryContext(surface="ci", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(conversation=state or {}),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="daily-regression"),
        config={
            "webhook-url": os.environ.get("N8N_WEBHOOK_URL", "http://127.0.0.1:5678/webhook/langbot-n8n-smoke"),
            "auth-type": "none",
            "output-key": "response",
            "response-handling": "reply",
            "timeout": 30,
        },
    )


def _kind(result) -> str:
    return getattr(result.type, "value", str(result.type))


def _summary_path() -> Path:
    return Path(os.environ.get("N8N_LIVE_OUTPUT", ".qa/n8n-live/summary.json"))


def _write_summary(payload: dict) -> None:
    path = _summary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _assert_run(results, *, expect_state_updates: bool) -> str:
    types = [_kind(result) for result in results]
    final_chunks = [
        result.data["chunk"]
        for result in results
        if _kind(result) == "message.delta" and result.data.get("chunk", {}).get("is_final")
    ]
    if len(final_chunks) != 1:
        raise AssertionError(f"expected one final chunk, got {len(final_chunks)}: {types}")
    content = str(final_chunks[0].get("content") or "")
    if not content.startswith(f"{SENTINEL}|{SENTINEL}."):
        raise AssertionError(f"unexpected n8n response: {content}")
    if "|user_daily-regression|n8n_conversation_" not in content or "|n8n_session_" not in content:
        raise AssertionError(f"Runner payload/state fields missing: {content}")
    if types.count("state.updated") != (2 if expect_state_updates else 0):
        raise AssertionError(f"unexpected state updates: {types}")
    if types[-1] != "run.completed":
        raise AssertionError(f"Runner did not complete: {types}")
    return content


async def _run() -> None:
    module, saved_modules = _load_runner()
    try:
        runner = object.__new__(module.DefaultRunner)
        first = [result async for result in runner.run(_context())]
        first_content = _assert_run(first, expect_state_updates=True)
        state = {result.data["key"]: result.data["value"] for result in first if _kind(result) == "state.updated"}
        second = [result async for result in runner.run(_context(state))]
        second_content = _assert_run(second, expect_state_updates=False)
        if second_content != first_content:
            raise AssertionError("persisted n8n conversation/session state changed the response")
        _write_summary(
            {
                "passed": True,
                "runner": "DefaultRunner",
                "turns": 2,
                "state_keys": sorted(state),
                "final_content": first_content,
            }
        )
        print(f"n8n latest Agent Runner regression passed: state_keys={sorted(state)}")
    finally:
        sys.path.remove(str(PLUGIN))
        for key in list(sys.modules):
            if key == "pkg" or key.startswith("pkg."):
                del sys.modules[key]
        sys.modules.update(saved_modules)


def main() -> int:
    try:
        asyncio.run(_run())
    except Exception as exc:
        _write_summary({"passed": False, "error": str(exc)})
        print(f"n8n latest Agent Runner regression failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
