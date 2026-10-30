"""Two installations drive one HelloPlugin object graph under shared-runtime-v1.

HelloPlugin relies on the stateless component model: one ``HelloPlugin`` and one
object per declared component serve every installation of the artifact digest.
These tests instantiate the real plugin/component classes, attach the same
component object to a task-local invocation for two distinct
``InstallationBinding`` values, and assert that each call builds everything from
its arguments and the invocation, retaining no tenant state on the shared object.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.entities import events
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import components.event_listener.default as default_mod  # noqa: E402
import components.tools.get_weather_alerts as weather_mod  # noqa: E402
from main import HelloPlugin  # noqa: E402


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


def _wire(component):
    """Mimic the runtime object graph: one plugin and one shared component."""
    plugin = HelloPlugin()
    handler = SimpleNamespace()
    plugin.plugin_runtime_handler = handler
    component.plugin = plugin
    return plugin, handler, component


def test_tool_is_stateless_and_resolves_config_per_invocation(monkeypatch):
    _plugin, handler, tool = _wire(weather_mod.GetWeatherAlerts())
    seen_urls: list[str] = []

    async def fake_request(url: str):
        seen_urls.append(url)
        return {"features": [{"properties": {"event": url.rsplit("/", 1)[-1]}}]}

    monkeypatch.setattr(weather_mod, "make_nws_request", fake_request)

    async def call(state: str, binding: InstallationBinding, config: dict) -> str:
        with bind_invocation(handler, config=config, binding=binding):
            # The same shared object yields the config of the active installation.
            assert tool.get_plugin_config() == config
            return await tool.call({"state": state})

    first = asyncio.run(call("CA", _binding("installation-a"), {"marker": "a"}))
    second = asyncio.run(call("NY", _binding("installation-b"), {"marker": "b"}))

    assert seen_urls == [
        "https://api.weather.gov/alerts/active/area/CA",
        "https://api.weather.gov/alerts/active/area/NY",
    ]
    assert "CA" in first and "NY" in second
    assert "NY" not in first and "CA" not in second
    # No per-invocation or tenant value was copied onto the shared component.
    assert set(vars(tool)) == {"plugin"}


def test_listener_handlers_mutate_only_the_per_event_context():
    _plugin, handler, listener = _wire(default_mod.DefaultEventListener())

    def make_context() -> SimpleNamespace:
        return SimpleNamespace(event=SimpleNamespace(user_message_alter=None))

    async def dispatch(event_context: SimpleNamespace, binding: InstallationBinding) -> None:
        with bind_invocation(handler, config={}, binding=binding):
            for registered in listener.registered_handlers[events.GroupNormalMessageReceived]:
                await registered(event_context)

    context_a = make_context()
    context_b = make_context()
    asyncio.run(dispatch(context_a, _binding("installation-a")))
    asyncio.run(dispatch(context_b, _binding("installation-b")))

    assert context_a.event.user_message_alter.text == "Hello from LangBot Plugin!"
    assert context_b.event.user_message_alter.text == "Hello from LangBot Plugin!"
    assert context_a.event.user_message_alter is not context_b.event.user_message_alter
    # The listener holds only its handler registry and plugin reference.
    assert set(vars(listener)) == {"registered_handlers", "plugin"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
