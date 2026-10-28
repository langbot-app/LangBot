"""Two installations drive one AutoTranslate object graph under shared-runtime-v1.

AutoTranslate relies on the stateless component model: the ``Translator`` listener
reads ``plugin.get_config()`` and resolves the LLM model for every event, so one
shared plugin/listener serves every installation. These tests drive the same
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

import components.event_listener.translator as translator_mod  # noqa: E402
from main import AutoTranslate  # noqa: E402


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
    plugin = AutoTranslate()
    handler = SimpleNamespace()
    plugin.plugin_runtime_handler = handler
    listener = translator_mod.Translator()
    listener.plugin = plugin
    return plugin, handler, listener


def _make_context(text: str) -> SimpleNamespace:
    context = SimpleNamespace(
        event=SimpleNamespace(message_chain=[platform_message.Plain(text=text)]),
        replies=[],
    )

    async def reply(message_chain):
        context.replies.append(message_chain)

    context.reply = reply
    return context


def test_config_and_model_are_resolved_per_event(monkeypatch):
    plugin, handler, listener = _wire()
    calls: list[tuple[str, str, str]] = []

    async def fake_translate(text: str, model_uuid: str, target_lang: str):
        calls.append((text, model_uuid, target_lang))
        return f"{target_lang}:{text}"

    monkeypatch.setattr(plugin, "translate", fake_translate)
    config_a = {"target_language": "en_US", "model": "model-a", "min_text_length": 4}
    config_b = {"target_language": "ja_JP", "model": "model-b", "min_text_length": 4}

    async def dispatch(context: SimpleNamespace, binding: InstallationBinding, config: dict) -> None:
        with bind_invocation(handler, config=config, binding=binding):
            await listener._handle_message(context, is_group=True)

    context_a = _make_context("Bonjour tout le monde")
    context_b = _make_context("Bonjour tout le monde")
    asyncio.run(dispatch(context_a, _binding("installation-a"), config_a))
    asyncio.run(dispatch(context_b, _binding("installation-b"), config_b))

    assert calls == [
        ("Bonjour tout le monde", "model-a", "en_US"),
        ("Bonjour tout le monde", "model-b", "ja_JP"),
    ]
    assert context_a.replies[0][0].text == "🌐 en_US:Bonjour tout le monde"
    assert context_b.replies[0][0].text == "🌐 ja_JP:Bonjour tout le monde"
    # Nothing from the invocation was stored on the shared listener or plugin.
    assert set(vars(listener)) == {"registered_handlers", "plugin"}
    assert plugin._legacy_config == {}


def test_private_gating_and_model_fallback_are_per_invocation(monkeypatch):
    plugin, handler, listener = _wire()
    calls: list[tuple[str, str, str]] = []

    async def fake_translate(text: str, model_uuid: str, target_lang: str):
        calls.append((text, model_uuid, target_lang))
        return f"{target_lang}:{text}"

    async def fake_models():
        return ["fallback-model"]

    monkeypatch.setattr(plugin, "translate", fake_translate)
    monkeypatch.setattr(plugin, "get_llm_models", fake_models)

    async def dispatch(context, binding, config, *, is_group):
        with bind_invocation(handler, config=config, binding=binding):
            await listener._handle_message(context, is_group=is_group)

    # installation-a disables private chat: a private message is ignored.
    private_a = _make_context("Bonjour tout le monde")
    asyncio.run(
        dispatch(
            private_a,
            _binding("installation-a"),
            {"target_language": "en_US", "enable_private": False, "min_text_length": 4},
            is_group=False,
        )
    )
    assert calls == []
    assert private_a.replies == []

    # installation-b enables private chat and declares no model: it falls back to
    # the invocation's first available model.
    private_b = _make_context("Bonjour tout le monde")
    asyncio.run(
        dispatch(
            private_b,
            _binding("installation-b"),
            {"target_language": "en_US", "enable_private": True, "min_text_length": 4},
            is_group=False,
        )
    )
    assert calls == [("Bonjour tout le monde", "fallback-model", "en_US")]
    assert private_b.replies[0][0].text == "🌐 en_US:Bonjour tout le monde"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
