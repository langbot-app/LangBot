"""Two installations drive one WordFSRS object graph under shared-runtime-v1.

There is no full SDK worker harness for misc plugins, so this drives the real
``bind_invocation`` + ``InstallationBinding`` envelope against one process-wide
plugin object (the object the shared runtime reuses for every installation) and
a Host stub that scopes the plugin KV store by workspace the way the Host does.

Assertions that fail on the pre-fix revision 0.2.2 (each was executed against it):

* ``test_two_installations_read_their_own_language_and_daily_limit`` -- the old
  ``initialize()`` copied ``get_config()`` (empty under shared placement) into
  ``self.language`` / ``self.daily_new_limit``, so installation B rendered with
  the code defaults: ``get_language() == "en_US"`` instead of ``"zh_Hans"`` and
  ``Today's new: 0 / 20`` instead of ``0 / 不限``.
* ``test_grade_uses_the_invoking_installations_desired_retention`` -- the old
  code built a single ``Scheduler`` in ``initialize()`` from the same empty
  config, so both installations scheduled from the 0.9 default instead of their
  own 0.7 / 0.97.
* ``test_concurrent_grades_on_one_session_do_not_lose_a_card`` -- the old deck
  read-modify-write had no lock, so of two concurrent grades one update was
  dropped (that card kept ``reviews == 0`` and the new-card counter advanced
  once).
* ``test_same_workspace_installations_keep_separate_decks`` -- the old storage
  key ``deck:{session}`` carried no installation scope, so two installations in
  one Workspace sharing a launcher id read and wrote one deck.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from main import WordFSRSPlugin  # noqa: E402

SESSION = "person:10001"

# Per-installation settings as the Host persists them; every value differs so
# cross-installation leakage is visible in the rendered message.
CONFIGS = {
    "a": {"language": "en_US", "daily_new_limit": 1, "desired_retention": 0.7},
    "b": {"language": "zh_Hans", "daily_new_limit": 0, "desired_retention": 0.97},
}


def _scope(owner: str, workspace: str | None = None) -> str:
    return f"instance-1:{workspace or f'workspace-{owner}'}:installation-{owner}"


def _deck_key(owner: str, workspace: str | None = None) -> str:
    """Deck row key: the installation scope must live in the plugin's own key."""
    return f"deck:{_scope(owner, workspace)}:{SESSION}"


LEGACY_DECK_KEY = f"deck:{SESSION}"


def _binding(
    installation: str,
    *,
    workspace: str | None = None,
    instance: str = "instance-1",
    revision: int = 1,
) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid=instance,
        workspace_uuid=workspace or f"workspace-{installation}",
        installation_uuid=f"installation-{installation}",
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


class _Host:
    """Minimal Host stand-in for plugin KV storage.

    Rows are scoped by workspace, exactly like the Host table
    ``[instance_uuid, workspace_uuid, owner_type, owner, key]``. A read returns
    the value as of the moment the Host receives it (plus round-trip latency),
    which is what makes an unguarded read-modify-write observably lose data.
    """

    def __init__(self, io_delay: float = 0.0) -> None:
        self.storage: dict[tuple[str, str], bytes] = {}
        self.io_delay = io_delay
        self.calls: list[str] = []

    async def call_action(self, action, data, *args, **kwargs):
        name = action.value if hasattr(action, "value") else str(action)
        binding = current_binding(self)
        workspace = binding.workspace_uuid if binding is not None else "-"
        key = data["key"]
        self.calls.append(f"{workspace}:{name}:{key}")
        if name == "get_plugin_storage":
            raw = self.storage.get((workspace, key), b"")
            await asyncio.sleep(self.io_delay)
            return {"value_base64": base64.b64encode(raw).decode("ascii")}
        if name == "set_plugin_storage":
            value = base64.b64decode(data["value_base64"])
            await asyncio.sleep(self.io_delay)
            self.storage[(workspace, key)] = value
            return {}
        raise AssertionError(f"unexpected Host action: {name}")

    def load(self, workspace: str, key: str) -> dict:
        return json.loads(self.storage[(workspace, key)])

    def deck(self, owner: str, workspace: str | None = None) -> dict:
        """Read one installation's deck row.

        Falls back to the historical unscoped row when the scoped row is absent,
        so a revision that ignores the installation scope fails on the deck
        assertion below instead of on this lookup.
        """
        ws = workspace or f"workspace-{owner}"
        key = _deck_key(owner, workspace)
        if (ws, key) not in self.storage:
            key = LEGACY_DECK_KEY
        return self.load(ws, key)

    def keys(self) -> list[tuple[str, str]]:
        return sorted(self.storage)


def _shared_plugin(host: _Host) -> WordFSRSPlugin:
    """One process-wide plugin object, as the shared worker builds it."""
    plugin = WordFSRSPlugin()
    plugin.plugin_runtime_handler = host
    plugin.config = {}  # ATTACH binds an empty config for the shared object graph
    return plugin


def test_two_installations_read_their_own_language_and_daily_limit():
    async def scenario():
        host = _Host()
        plugin = _shared_plugin(host)
        await plugin.initialize()  # process-scoped only; must capture no tenant config
        assert "language" not in vars(plugin)
        assert "scheduler" not in vars(plugin)

        observed = {}
        for owner in ("a", "b"):
            with bind_invocation(host, config=CONFIGS[owner], binding=_binding(owner)):
                await plugin.add_word(SESSION, "apple", "apple")
                observed[owner] = (plugin.get_language(), await plugin.stats(SESSION))
        return observed

    observed = asyncio.run(scenario())

    assert observed["a"][0] == "en_US"
    assert "Today's new: 0 / 1" in observed["a"][1]
    assert observed["b"][0] == "zh_Hans"
    assert "今日新词：0 / 不限" in observed["b"][1]


def test_grade_uses_the_invoking_installations_desired_retention():
    async def schedule(owner: str, host: _Host, plugin: WordFSRSPlugin) -> datetime:
        with bind_invocation(host, config=CONFIGS[owner], binding=_binding(owner)):
            await plugin.add_word(SESSION, "apple")
            # "easy" graduates a new card on the first review, so the next due
            # date comes from desired_retention instead of a fixed learning step.
            await plugin.grade(SESSION, "apple", "4")
        due = host.deck(owner)["cards"]["apple"]["fsrs"]["due"]
        return datetime.fromisoformat(due)

    async def scenario():
        host = _Host()
        plugin = _shared_plugin(host)
        await plugin.initialize()
        return await schedule("a", host, plugin), await schedule("b", host, plugin)

    due_low_retention, due_high_retention = asyncio.run(scenario())

    # Same fresh card, same rating: only desired_retention differs. py-fsrs
    # applies a few percent of interval fuzz, so the assertion uses wide bands
    # instead of an exact interval: 0.7 schedules tens of days out, 0.97 about
    # a day. With the pre-fix code-default 0.9 both installations land on the
    # same ~8 days and both bounds fail.
    now = datetime.now(timezone.utc)
    assert due_low_retention > now + timedelta(days=30)
    assert due_high_retention < now + timedelta(days=5)


def test_concurrent_grades_on_one_session_do_not_lose_a_card():
    async def scenario():
        host = _Host(io_delay=0.005)
        plugin = _shared_plugin(host)
        await plugin.initialize()
        with bind_invocation(host, config=CONFIGS["a"], binding=_binding("a")):
            await plugin.add_word(SESSION, "apple")
            await plugin.add_word(SESSION, "banana")
            await asyncio.gather(
                plugin.grade(SESSION, "apple", "3"),
                plugin.grade(SESSION, "banana", "3"),
            )
        return host.deck("a")

    deck = asyncio.run(scenario())

    # Both cards are still there and both updates survived the overlapping commands.
    assert set(deck["cards"]) == {"apple", "banana"}
    assert deck["cards"]["apple"]["reviews"] == 1
    assert deck["cards"]["banana"]["reviews"] == 1
    assert sum(deck["new_intro"].values()) == 2


def test_revocation_releases_only_that_installations_lock():
    async def scenario():
        host = _Host()
        plugin = _shared_plugin(host)
        for owner in ("a", "b"):
            with bind_invocation(host, config=CONFIGS[owner], binding=_binding(owner)):
                await plugin.add_word(SESSION, "apple")
        assert len(plugin._deck_locks) == 2
        await plugin.on_installation_revoked(_binding("a"))
        return plugin

    plugin = asyncio.run(scenario())

    assert set(plugin._deck_locks) == {_scope("b")}


def test_same_workspace_installations_keep_separate_decks():
    """Host rows have no installation dimension: the plugin key must carry it."""

    async def scenario():
        host = _Host()
        plugin = _shared_plugin(host)
        await plugin.initialize()
        shared_workspace = "workspace-shared"
        for owner in ("a", "b"):
            with bind_invocation(
                host,
                config=CONFIGS[owner],
                binding=_binding(owner, workspace=shared_workspace),
            ):
                await plugin.add_word(SESSION, f"word-{owner}")
        return host, plugin

    host, plugin = asyncio.run(scenario())

    assert host.keys() == [
        ("workspace-shared", _deck_key("a", "workspace-shared")),
        ("workspace-shared", _deck_key("b", "workspace-shared")),
    ]
    deck_a = host.deck("a", "workspace-shared")
    deck_b = host.deck("b", "workspace-shared")
    assert set(deck_a["cards"]) == {"word-a"}
    assert set(deck_b["cards"]) == {"word-b"}

    # Each installation reads back only its own deck through the same object.
    async def listed(owner: str) -> str:
        with bind_invocation(
            host,
            config=CONFIGS[owner],
            binding=_binding(owner, workspace="workspace-shared"),
        ):
            return await plugin.list_words(SESSION)

    assert "word-a" in asyncio.run(listed("a"))
    assert "word-b" not in asyncio.run(listed("a"))


def test_dedicated_worker_without_a_binding_uses_the_legacy_row():
    """Binding-less placement keeps the historical unscoped row; no migration."""

    async def scenario():
        host = _Host()
        plugin = _shared_plugin(host)
        with bind_invocation(host, config=CONFIGS["a"], binding=_binding("a")):
            await plugin.add_word(SESSION, "shared-word")
        # No invocation and no binding: the dedicated shape.
        plugin.config = {"language": "en_US"}
        await plugin.add_word(SESSION, "legacy-word")
        return host, plugin

    host, plugin = asyncio.run(scenario())

    assert ("workspace-a", _deck_key("a")) in host.keys()
    assert ("-", LEGACY_DECK_KEY) in host.keys()
    # A legacy row stays a legacy row: the scoped row is not seeded from it
    # (and vice versa), so the two decks are independent.
    assert set(host.load("-", LEGACY_DECK_KEY)["cards"]) == {"legacy-word"}
    assert set(host.deck("a")["cards"]) == {"shared-word"}

    assert plugin._current_scope() == "dedicated"
    # The binding-less scope has its own guard, distinct from any installation's.
    assert set(plugin._deck_locks) == {_scope("a"), "dedicated"}


def test_dedicated_worker_config_is_still_honoured_without_a_binding():
    """Dedicated placement has no installation binding: the instance config applies."""

    async def scenario():
        host = _Host()
        plugin = WordFSRSPlugin()
        plugin.plugin_runtime_handler = host
        plugin.config = {
            "language": "zh_Hans",
            "daily_new_limit": 3,
            "desired_retention": 0.97,
        }
        await plugin.initialize()
        await plugin.add_word(SESSION, "apple")
        return plugin.get_language(), await plugin.stats(SESSION)

    language, stats = asyncio.run(scenario())

    assert language == "zh_Hans"
    assert "今日新词：0 / 3" in stats


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
