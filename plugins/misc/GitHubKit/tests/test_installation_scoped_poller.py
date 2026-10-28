"""Two installations of one artifact must not share subscriptions or pollers.

The real plugin object graph is a process-wide singleton, so these tests drive
**two distinct installation bindings through one GitHubKitPlugin object** with the
installed SDK's ``bind_invocation`` + ``InstallationBinding``. The synthetic Host
mirrors LangBot's durable plugin-storage row key
``[instance_uuid, workspace_uuid, owner_type, owner, key]``: it has **no
installation dimension**, so two installations in the same Workspace share a row
unless the plugin namespaces its own key. It is a synthetic KV, not a live
LangBot DB; ``_get`` is stubbed so no GitHub request is made.

Pre-fix failure (assertions marked ``PRE-FIX`` below): language/token/interval
were cached on the instance in ``initialize()``, one detached poller was started
with a process-global lock, and subscriptions lived under the bare
``subscriptions`` row, so installation B saw A's repo subscriptions, polled with
A's cached credentials and revoking A left its poller running.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from pathlib import Path

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

import main as plugin_main  # noqa: E402
from main import GitHubKitPlugin  # noqa: E402

SHARED_PROFILE_ENV = "LANGBOT_PLUGIN_RUNTIME_PROFILE"

INSTANCE = "instance-1"
WORKSPACE = "workspace-1"

CONFIG_A = {
    "language": "en_US",
    "github_token": "token-a",
    "poll_interval": 120,
    "max_events_per_push": 5,
}
CONFIG_B = {
    "language": "zh_Hans",
    "github_token": "token-b",
    "poll_interval": 300,
    "max_events_per_push": 2,
}


def _binding(installation: str, *, workspace: str = WORKSPACE) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=INSTANCE,
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


class FakeHost:
    """Synthetic Host worker carrying durable plugin rows, keyed like the real one."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], bytes] = {}
        self.writes: list[tuple[str, bytes]] = []
        self.sent: list[dict] = []
        self.bound_action_context = None

    def _scope(self) -> tuple[str, str]:
        binding = current_binding(self)
        if binding is not None:
            return binding.instance_uuid, binding.workspace_uuid
        assert self.bound_action_context is not None, "no execution scope bound"
        return (
            self.bound_action_context.instance_uuid,
            self.bound_action_context.workspace_uuid,
        )

    async def call_action(self, action, data):
        instance, workspace = self._scope()
        if action == Action.SEND_MESSAGE:
            self.sent.append(data)
            return {"result": None}
        if action == Action.GET_PLUGIN_STORAGE_KEYS:
            return {
                "keys": [k for i, w, k in self.rows if (i, w) == (instance, workspace)]
            }
        key = data["key"]
        row = (instance, workspace, key)
        if action == Action.GET_PLUGIN_STORAGE:
            return {"value_base64": base64.b64encode(self.rows[row]).decode()}
        if action == Action.SET_PLUGIN_STORAGE:
            value = base64.b64decode(data["value_base64"])
            self.writes.append((key, value))
            self.rows[row] = value
            return {}
        if action == Action.DELETE_PLUGIN_STORAGE:
            del self.rows[row]
            return {}
        raise AssertionError(action)


def _plugin(host: FakeHost) -> GitHubKitPlugin:
    plugin = GitHubKitPlugin()
    plugin.plugin_runtime_handler = host
    return plugin


def _stub_get(plugin: GitHubKitPlugin, seen: list[tuple[str, str | None]]) -> None:
    """Replace the GitHub transport: no network, tokens recorded per call."""

    async def fake_get(path, params=None, *, token=None):
        seen.append((path, token))
        if path.endswith("/events"):
            return 200, [{"id": "100"}], {}
        return 200, {"full_name": path.strip("/"), "default_branch": "main"}, {}

    plugin._get = fake_get  # type: ignore[assignment]


async def _subscribe(plugin: GitHubKitPlugin, repo: str, session: str) -> str:
    return await plugin.subscribe(
        repo, session, "bot-uuid", "group", session, None
    )


def test_each_installation_sees_only_its_own_subscriptions_and_credentials():
    """One object graph, two bindings: no subscription or credential crosses over."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        seen: list[tuple[str, str | None]] = []
        _stub_get(plugin, seen)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _subscribe(plugin, "owner/repo-a", "session-a")
            assert plugin.get_language() == "en_US"
        tokens_a = {token for _, token in seen}
        seen.clear()

        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            # PRE-FIX: B listed A's "owner/repo-a" and used A's cached token.
            assert "owner/repo-a" not in await plugin.list_subscriptions("session-a")
            await _subscribe(plugin, "owner/repo-b", "session-b")
            assert plugin.get_language() == "zh_Hans"
        assert {token for _, token in seen} == {"token-b"}
        seen.clear()

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            listing = await plugin.list_subscriptions("session-a")
            assert "owner/repo-a" in listing
            # PRE-FIX: A also saw B's "owner/repo-b".
            assert "owner/repo-b" not in listing
        # The poller belongs to the invoking installation only.
        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._pollers) == {scope_a, scope_b}
        assert plugin._pollers[scope_a].config["poll_interval"] == 120
        assert plugin._pollers[scope_a].config["token"] == "token-a"
        assert plugin._pollers[scope_b].config["poll_interval"] == 300
        assert plugin._pollers[scope_b].config["token"] == "token-b"

        # Durable rows are namespaced by installation inside the shared Host row.
        keys = {key for key, _ in host.writes}
        assert keys == {f"subscriptions:{scope_a}", f"subscriptions:{scope_b}"}
        # PRE-FIX: the single bare "subscriptions" row was shared by both.
        assert "subscriptions" not in keys

        await plugin.destroy()

    asyncio.run(scenario())


def test_one_poll_cycle_pushes_only_to_the_owning_installation(monkeypatch):
    """The real poller loop polls and pushes for exactly one installation."""

    async def scenario():
        monkeypatch.setattr(plugin_main, "POLL_START_DELAY", 0)
        host = FakeHost()
        plugin = _plugin(host)
        seen: list[tuple[str, str | None]] = []

        event = {
            "id": "101",
            "type": "PushEvent",
            "actor": {"login": "octocat"},
            "payload": {
                "ref": "refs/heads/main",
                "size": 1,
                "commits": [{"message": "hi"}],
            },
        }

        async def fake_get(path, params=None, *, token=None):
            seen.append((path, token))
            if path.endswith("/events"):
                if params and params.get("per_page") == 1:
                    return 200, [{"id": "100"}], {}
                if path.endswith("/repos/owner/repo-a/events"):
                    return 200, [event, {"id": "100"}], {}
                return 200, [{"id": "100"}], {}
            return 200, {"full_name": path.strip("/")}, {}

        plugin._get = fake_get  # type: ignore[assignment]
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _subscribe(plugin, "owner/repo-a", "session-a")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await _subscribe(plugin, "owner/repo-b", "session-b")

        for _ in range(500):
            if host.sent:
                break
            await asyncio.sleep(0)

        # PRE-FIX: one shared poller used the last-cached token and pushed A's repo
        # events to whichever installation's subscriber map it happened to read.
        assert [m["target_id"] for m in host.sent] == ["session-a"]
        assert host.sent and host.sent[0]["target_type"] == "group"
        # The poll used installation A's own credentials, not B's.
        assert any(
            path.endswith("/repos/owner/repo-a/events") and token == "token-a"
            for path, token in seen
        )
        assert all(token != "token-b" for path, token in seen if "repo-a" in path)

        await plugin.destroy()

    asyncio.run(scenario())


def test_pollers_are_binding_keyed_and_stopped_on_revocation():
    """A revoked installation's poller is stopped; its sibling keeps polling."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        seen: list[tuple[str, str | None]] = []
        _stub_get(plugin, seen)
        binding_a = _binding("installation-a")
        binding_b = _binding("installation-b")

        with bind_invocation(host, config=CONFIG_A, binding=binding_a):
            await _subscribe(plugin, "owner/repo-a", "session-a")
        with bind_invocation(host, config=CONFIG_B, binding=binding_b):
            await _subscribe(plugin, "owner/repo-b", "session-b")

        scope_a = plugin_main.installation_scope(binding_a)
        scope_b = plugin_main.installation_scope(binding_b)
        assert set(plugin._pollers) == {scope_a, scope_b}
        task_a = plugin._pollers[scope_a].task
        task_b = plugin._pollers[scope_b].task
        assert task_a is not None and task_b is not None
        assert not task_a.done() and not task_b.done()

        await plugin.on_installation_revoked(binding_a)
        # PRE-FIX: the single detached poller had no registry, so it kept running
        # (and kept using the revoked tenant's credentials).
        assert scope_a not in plugin._pollers
        assert task_a.cancelled()
        assert scope_b in plugin._pollers
        assert not task_b.done()

        await plugin.on_installation_revoked(binding_b)
        assert plugin._pollers == {}
        assert task_b.cancelled()

    asyncio.run(scenario())


def test_initialize_is_process_scoped_and_keeps_subscriptions_intact():
    """initialize() runs once per worker with no config; it must not reset a tenant."""

    async def scenario():
        host = FakeHost()
        plugin = _plugin(host)
        seen: list[tuple[str, str | None]] = []
        _stub_get(plugin, seen)
        tenant = _binding("installation-a")

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            await _subscribe(plugin, "owner/repo-a", "session-a")
        writes_before = list(host.writes)
        pollers_before = dict(plugin._pollers)

        # The runtime calls initialize() with an empty config, outside any slot.
        await plugin.initialize()

        with bind_invocation(host, config=CONFIG_A, binding=tenant):
            # PRE-FIX: initialize() re-read the shared row and restarted the poller
            # with an empty token/interval.
            assert "owner/repo-a" in await plugin.list_subscriptions("session-a")
        assert host.writes == writes_before
        assert plugin._pollers == pollers_before

        await plugin.destroy()

    asyncio.run(scenario())


def test_dedicated_binding_less_worker_keeps_the_legacy_key(monkeypatch):
    """Dedicated placement has no invocation binding and must keep its stored rows."""

    async def scenario():
        host = FakeHost()
        host.bound_action_context = ActionContext(
            instance_uuid=INSTANCE,
            workspace_uuid=WORKSPACE,
            placement_generation=1,
        )
        plugin = _plugin(host)
        seen: list[tuple[str, str | None]] = []
        _stub_get(plugin, seen)

        monkeypatch.delenv(SHARED_PROFILE_ENV, raising=False)
        with bind_invocation(host, config=CONFIG_A):
            await _subscribe(plugin, "owner/repo-a", "session-a")
            listing = await plugin.list_subscriptions("session-a")
        assert "owner/repo-a" in listing
        assert {key for key, _ in host.writes} == {"subscriptions"}

        await plugin.destroy()

    asyncio.run(scenario())


def test_shared_profile_without_binding_refuses(monkeypatch):
    """A shared worker with no trusted binding must not fall back to a shared key."""

    host = FakeHost()
    plugin = _plugin(host)
    monkeypatch.setenv(SHARED_PROFILE_ENV, "shared")

    with pytest.raises(RuntimeError):
        asyncio.run(plugin.list_subscriptions("session-a"))
    assert host.writes == []
