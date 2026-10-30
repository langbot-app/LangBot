"""Two installations drive one URLSummary object graph under shared-runtime-v1.

URLSummary relies on the stateless component model: the ``URLDetector`` listener
reads ``plugin.get_config()`` per event and every fetch binds its own
target-validated connection (see ``safe_fetch.py``). These tests drive the same
component object across two distinct ``InstallationBinding`` values.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import main as main_mod  # noqa: E402
from components.event_listener.url_detector import URLDetector  # noqa: E402
from main import URLSummary  # noqa: E402


def _binding(
    installation: str,
    *,
    workspace: str = "workspace-1",
    instance: str = "instance-1",
    revision: int = 1,
) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def _wire():
    """Mimic the runtime object graph: one plugin and one shared listener."""
    plugin = URLSummary()
    handler = SimpleNamespace()
    plugin.plugin_runtime_handler = handler
    listener = URLDetector()
    listener.plugin = plugin
    return plugin, handler, listener


def _make_context(text: str) -> SimpleNamespace:
    context = SimpleNamespace(
        event=SimpleNamespace(message_chain=[platform_message.Plain(text=text)]),
        replies=[],
    )

    def prevent_default():
        context.prevent_default_called = True

    def prevent_postorder():
        context.prevent_postorder_called = True

    async def reply(message_chain):
        context.replies.append(message_chain)

    context.prevent_default = prevent_default
    context.prevent_postorder = prevent_postorder
    context.reply = reply
    return context


def test_config_model_and_summary_are_resolved_per_event(monkeypatch):
    plugin, handler, listener = _wire()
    fetches: list[tuple[str, int]] = []
    summaries: list[tuple[str, str, str]] = []

    async def fake_fetch(url: str, max_len: int):
        fetches.append((url, max_len))
        return "Title", "x" * 120

    async def fake_summarize(url: str, title: str, content: str, model_uuid: str, language: str):
        summaries.append((url, model_uuid, language))
        return f"summary:{language}:{model_uuid}"

    monkeypatch.setattr(plugin, "fetch_page", fake_fetch)
    monkeypatch.setattr(plugin, "summarize", fake_summarize)

    async def dispatch(context: SimpleNamespace, binding: InstallationBinding, config: dict) -> None:
        with bind_invocation(handler, config=config, binding=binding):
            await listener._handle_message(context)

    context_a = _make_context("look https://example.com/a")
    context_b = _make_context("look https://example.com/b")
    asyncio.run(
        dispatch(
            context_a,
            _binding("installation-a"),
            {"max_content_length": 111, "language": "en_US", "model": "model-a"},
        )
    )
    asyncio.run(
        dispatch(
            context_b,
            _binding("installation-b"),
            {"max_content_length": 222, "language": "ja_JP", "model": "model-b"},
        )
    )

    assert fetches == [("https://example.com/a", 111), ("https://example.com/b", 222)]
    assert summaries == [
        ("https://example.com/a", "model-a", "en_US"),
        ("https://example.com/b", "model-b", "ja_JP"),
    ]
    assert context_a.replies[0][0].text == "📄 Title\n\nsummary:en_US:model-a"
    assert context_b.replies[0][0].text == "📄 Title\n\nsummary:ja_JP:model-b"
    # Nothing from the invocation was stored on the shared listener or plugin.
    assert set(vars(listener)) == {"registered_handlers", "plugin"}
    assert plugin._legacy_config == {}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
