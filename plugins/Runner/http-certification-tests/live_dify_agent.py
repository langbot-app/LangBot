"""Live Dify Cloud regression for the Dify Agent Runner."""

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
PLUGIN = ROOT / "dify-agent"
SENTINEL = "LANGBOT_DIFY_DAILY_OK"


def _load_runner():
    saved = {key: value for key, value in sys.modules.items() if key == "pkg" or key.startswith("pkg.")}
    for key in saved:
        del sys.modules[key]
    sys.path.insert(0, str(PLUGIN))
    try:
        spec = importlib.util.spec_from_file_location("live_dify_agent_runner", PLUGIN / "components/runner/default.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load Dify Agent runner")
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


def _context() -> RunnerContext:
    return RunnerContext(
        run_id="dify-cloud-daily-regression",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="dify-cloud-daily-regression", event_type="message.received", source="ci"),
        conversation=ConversationContext(conversation_id="daily-regression", session_id="daily-regression"),
        input=AgentInput(text=f"Reply with exactly {SENTINEL} and nothing else. Do not call tools."),
        delivery=DeliveryContext(surface="ci", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="daily-regression"),
        config={},
    )


def _kind(result) -> str:
    return getattr(result.type, "value", str(result.type))


def _summary_path() -> Path:
    return Path(os.environ.get("DIFY_LIVE_OUTPUT", ".qa/dify-live/summary.json"))


def _write_summary(payload: dict) -> None:
    path = _summary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _run() -> None:
    api_key = os.environ.get("DIFY_AGENT_API_KEY", "")
    base_url = os.environ.get("DIFY_AGENT_BASE_URL", "https://api.dify.ai/v1")
    timeout = float(os.environ.get("DIFY_AGENT_TIMEOUT", "120"))
    if not api_key:
        raise RuntimeError("DIFY_AGENT_API_KEY is required for the live regression")

    module, saved_modules = _load_runner()
    try:
        client = module.AsyncDifyClient(api_key=api_key, base_url=base_url, timeout=timeout)
        event_types: list[str] = []

        class ObservedClient:
            base_url = client.base_url

            async def chat_messages(self, **kwargs):
                async for event in client.chat_messages(**kwargs):
                    event_types.append(str(event.get("event", "")))
                    yield event

        runner = object.__new__(module.DefaultRunner)
        context = _context()
        results = [
            result
            async for result in runner._run_chat_or_agent(
                context,
                ObservedClient(),
                {},
                context.input.to_text(),
                "langbot-daily-regression",
                "",
                [],
                "agent",
                False,
            )
        ]
        final_chunks = [
            result.data["chunk"]
            for result in results
            if _kind(result) == "message.delta" and result.data.get("chunk", {}).get("is_final")
        ]
        final_text = "".join(str(chunk.get("content") or "") for chunk in final_chunks)
        required_events = {"agent_message", "message", "message_end"}
        missing_events = sorted(required_events.difference(event_types))
        if missing_events:
            raise AssertionError(f"Dify Agent stream did not include required events: {missing_events}")
        if len(final_chunks) != 1:
            raise AssertionError(f"expected exactly one final message chunk, got {len(final_chunks)}")
        if final_text.count(SENTINEL) != 1:
            raise AssertionError("final Dify answer was missing or repeated")
        if not any(_kind(result) == "run.completed" for result in results):
            raise AssertionError("Dify Agent run did not complete")

        _write_summary(
            {
                "passed": True,
                "event_types": event_types,
                "final_chunk_count": len(final_chunks),
                "sentinel_count": final_text.count(SENTINEL),
            }
        )
        print(f"Dify live regression passed: events={event_types}; final_chunks={len(final_chunks)}")
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
        api_key = os.environ.get("DIFY_AGENT_API_KEY", "")
        message = str(exc).replace(api_key, "<redacted>") if api_key else str(exc)
        _write_summary({"passed": False, "error": message})
        print(f"Dify live regression failed: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
