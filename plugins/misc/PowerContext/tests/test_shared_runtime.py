"""Two installations must not share one PowerContext credential or endpoint.

Pre-fix failure this test pins: ``PowerContextPlugin.initialize()`` copied every
config value into instance attributes and built a single ``PowerContextClient``
for the process, so with ``CONFIG_A`` attached first the second installation's
invocation sent ``token-a`` to ``http://127.0.0.1:9101``. The assertions below
(``every request carries this installation's own token``) fail on that code.

Both installations are driven through the *same* plugin object and the *same*
``ContextBridge`` component object, under the real SDK ``bind_invocation`` /
``InstallationBinding`` task-local scope, with only the per-binding config
differing.

A second pinned pre-fix failure (F-01): ``resolve_settings()`` fell back to the
process-global ``POWERCONTEXT_CLIENT_API_TOKEN`` when ``api_token`` was empty,
so any installation could pair that worker credential with a ``server_url`` it
chose. ``test_process_environment_token_is_never_sent_to_a_tenant_server`` and
``test_resolve_settings_takes_the_token_only_from_invocation_config`` fail on
that code.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.event_listener.context_bridge import ContextBridge  # noqa: E402
from main import PowerContextPlugin, resolve_settings  # noqa: E402

CONFIG_A = {
    "server_url": "http://127.0.0.1:9101",
    "api_token": "token-a",
    "scope_mode": "session",
}
CONFIG_B = {
    "server_url": "http://127.0.0.1:9102",
    "api_token": "token-b",
    "scope_mode": "bot",
}

RECORD: list[dict[str, Any]] = []


def _binding(installation: str, *, revision: int = 1) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=f"workspace-{installation}",
        installation_uuid=installation,
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def _payload_for(path: str, token: str) -> dict[str, Any]:
    if path == "/v1/scope-bindings/resolve":
        return {"scope_id": f"scope-for-{token}"}
    if path == "/v1/context/prepare":
        return {"status": "empty", "content": None, "content_bytes": 0}
    if path == "/v1/sources/content":
        return {"status": "accepted"}
    raise AssertionError(f"unexpected PowerContext path {path}")


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _RecordingAsyncClient:
    """Stands in for httpx.AsyncClient to capture endpoint and bearer token."""

    def __init__(self, **kwargs: Any) -> None:
        self._base_url = str(kwargs["base_url"])
        self._headers = dict(kwargs.get("headers") or {})

    async def __aenter__(self) -> "_RecordingAsyncClient":
        return self

    async def __aexit__(self, *_exc: Any) -> bool:
        return False

    async def request(self, method: str, path: str, json: Any = None):
        authorization = self._headers.get("Authorization")
        token = str(authorization or "").removeprefix("Bearer ")
        RECORD.append(
            {
                "base_url": self._base_url,
                "authorization": authorization,
                "token": token,
                "path": path,
                "json": json,
            }
        )
        return _FakeResponse(_payload_for(path, token))


class _EventContext:
    query_id = 9
    query_uuid = "query-uuid"

    def __init__(self, text: str) -> None:
        self.event = SimpleNamespace(session_name="person_1", prompt=[])
        self.state: dict[str, Any] | None = None
        self._text = text

    async def get_query_vars(self):
        return {
            "user_message_text": self._text,
            "sender_id": "u1",
            "sender_name": "Alice",
        }

    async def get_bot_uuid(self):
        return "bot-1"

    async def set_query_var(self, key, value):
        assert key == "_powercontext_context"
        self.state = value


@pytest.fixture(autouse=True)
def _reset_record():
    RECORD.clear()
    yield
    RECORD.clear()


@pytest.fixture
def recording_transport(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _RecordingAsyncClient)


@pytest.mark.asyncio
async def test_each_installation_uses_its_own_server_and_token(recording_transport) -> None:
    # One process-wide plugin object and one component object, as in a shared worker.
    handler = SimpleNamespace()
    plugin = PowerContextPlugin()
    plugin.plugin_runtime_handler = handler
    bridge = ContextBridge()
    bridge.plugin = plugin

    event_a = _EventContext("hello from A")
    with bind_invocation(handler, config=CONFIG_A, binding=_binding("installation-a")):
        await bridge._process_turn(event_a)

    requests_a = list(RECORD)
    RECORD.clear()

    event_b = _EventContext("hello from B")
    with bind_invocation(handler, config=CONFIG_B, binding=_binding("installation-b")):
        await bridge._process_turn(event_b)

    requests_b = list(RECORD)

    # Each installation's credentials and endpoint stayed in its own invocation.
    assert {entry["token"] for entry in requests_a} == {"token-a"}
    assert {entry["base_url"] for entry in requests_a} == {"http://127.0.0.1:9101"}
    assert {entry["token"] for entry in requests_b} == {"token-b"}
    assert {entry["base_url"] for entry in requests_b} == {"http://127.0.0.1:9102"}
    assert {entry["path"] for entry in requests_a} == {
        "/v1/scope-bindings/resolve",
        "/v1/context/prepare",
        "/v1/sources/content",
    }
    assert event_a.state is not None and event_a.state["scope_id"] == "scope-for-token-a"
    assert event_b.state is not None and event_b.state["scope_id"] == "scope-for-token-b"
    assert event_a.state["scope_mode"] == "session"
    assert event_b.state["scope_mode"] == "bot"

    # Nothing on the shared object retains a single tenant's configuration.
    assert not hasattr(plugin, "client")
    assert "token-a" not in repr(vars(plugin))
    assert "token-b" not in repr(vars(plugin))
    assert "9101" not in repr(vars(plugin))
    assert "9102" not in repr(vars(plugin))


def test_resolve_settings_takes_the_token_only_from_invocation_config(
    monkeypatch,
) -> None:
    # F-01: a process-global credential must not become any installation's token.
    monkeypatch.setenv("POWERCONTEXT_CLIENT_API_TOKEN", "env-token-leak")

    empty = resolve_settings({"server_url": "https://tenant.example", "api_token": ""})
    assert empty.api_token == ""
    configured = resolve_settings({"api_token": "configured-token"})
    assert configured.api_token == "configured-token"


@pytest.mark.asyncio
async def test_process_environment_token_is_never_sent_to_a_tenant_server(
    recording_transport, monkeypatch
) -> None:
    """One installation must not exfiltrate the worker's credential to its host.

    Pre-fix failure this test pins: with ``api_token`` empty, ``resolve_settings``
    fell back to ``os.environ["POWERCONTEXT_CLIENT_API_TOKEN"]`` and the bearer
    token was paired with whatever ``server_url`` the installation configured, so
    the recording transport below saw ``Bearer env-token-leak`` on
    ``http://127.0.0.1:9101`` — a host that installation chose.
    """

    handler = SimpleNamespace()
    plugin = PowerContextPlugin()
    plugin.plugin_runtime_handler = handler
    bridge = ContextBridge()
    bridge.plugin = plugin

    monkeypatch.setenv("POWERCONTEXT_CLIENT_API_TOKEN", "env-token-leak")
    config = {"server_url": "http://127.0.0.1:9101", "api_token": ""}

    with bind_invocation(handler, config=config, binding=_binding("installation-a")):
        await bridge._process_turn(_EventContext("hello"))

    # The configured Server is still called; it just receives no process credential.
    assert RECORD
    assert {entry["base_url"] for entry in RECORD} == {"http://127.0.0.1:9101"}
    assert [entry["authorization"] for entry in RECORD] == [None] * len(RECORD)
    assert all(entry["token"] == "" for entry in RECORD)
    assert "env-token-leak" not in repr(RECORD)


@pytest.mark.asyncio
async def test_dedicated_config_without_an_invocation_is_still_served(
    recording_transport,
) -> None:
    # Dedicated workers set the legacy config and call the same code path.
    plugin = PowerContextPlugin()
    plugin.plugin_runtime_handler = SimpleNamespace()
    plugin.config = {
        "server_url": "http://127.0.0.1:9300",
        "api_token": "dedicated-token",
        "auto_recall": False,
        "capture_user_messages": False,
    }

    settings = plugin.settings()
    assert settings.server_url == "http://127.0.0.1:9300"
    assert settings.api_token == "dedicated-token"
    assert settings.auto_recall is False
    assert settings.new_client().server_url == "http://127.0.0.1:9300"

    bridge = ContextBridge()
    bridge.plugin = plugin
    event = _EventContext("dedicated hello")
    await bridge._process_turn(event)

    assert event.state is not None and event.state["scope_id"] == "scope-for-dedicated-token"
    assert {entry["token"] for entry in RECORD} == {"dedicated-token"}
    assert {entry["path"] for entry in RECORD} == {"/v1/scope-bindings/resolve"}
