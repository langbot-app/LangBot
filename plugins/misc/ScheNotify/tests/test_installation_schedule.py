"""Two installations, one ScheNotify object: schedules never cross over.

Evidence model: the real SDK ``bind_invocation``/``InstallationBinding`` drive
two distinct installation bindings through one plugin object; the stub Host
records every ``SEND_MESSAGE`` relay it receives, so a notification fired for
the wrong installation is visible as an extra relay carrying the other
installation's reminder text.

Pre-fix failure (asserted below): the plugin kept one ``scheduled_events`` list
and one minute-loop on the process-wide object, created in ``initialize()``.
Installation B's ``get_scheduled_events`` therefore returned installation A's
reminders, and the single loop delivered both installations' reminders (the
loop also resolved config outside any invocation). ``on_installation_revoked``
released nothing because nothing was keyed by an installation.

Second-round findings, also asserted below:

* the detached scheduler ran in a fresh empty context and never re-established
  the scheduling installation's invocation, so the Host saw ``None`` as the
  binding of a relay that carried tenant data
  (``test_detached_send_runs_under_the_captured_installation_binding``);
* lookups deleted/listed by ``target_id`` alone, so another bot of the same
  installation, or the other namespace with the same id, was treated as the same
  session (``test_schedule_commands_do_not_reach_another_session`` and
  ``test_session_key_distinguishes_bot_and_namespace``);
* a failed send was swallowed and the reminder deleted anyway, the delivery loop
  iterated a mutable list across ``await``, and the queue was unbounded with its
  content dumped to debug logs (``test_failed_delivery_keeps_the_reminder_queued``,
  ``test_delivery_snapshot_survives_a_concurrent_delete``,
  ``test_queue_is_bounded_and_reminder_text_is_not_logged``).

The upgrade case (same scope token, new revision) is covered by
``test_worker_upgrade_restarts_the_loop_under_the_new_binding``.
"""

from __future__ import annotations

import asyncio
import datetime
import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes, Session
from langbot_plugin.api.proxies.invocation import bind_invocation, current_binding
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction as Action
from langbot_plugin.entities.io.context import InstallationBinding

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from components.commands.dsche import DscheCommand  # noqa: E402
from components.commands.sche import ScheCommand  # noqa: E402
from components.tools.schedule_notify import ScheduleNotify  # noqa: E402


def _load_main():
    spec = importlib.util.spec_from_file_location("schenotify_main", PLUGIN_ROOT / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sche_main = _load_main()


class FlatHost:
    """Stub Host that records notification relays (no live platform call)."""

    def __init__(self, *, fail_sends: int = 0, on_send=None):
        self.sent: list[dict] = []
        # Binding the relay was made under, as the real Host would resolve it.
        self.authorities: list = []
        self.fail_sends = fail_sends
        self.on_send = on_send

    async def call_action(self, action, data, *args, **kwargs):
        if action == Action.SEND_MESSAGE:
            self.authorities.append(current_binding(self))
            if self.fail_sends > 0:
                self.fail_sends -= 1
                raise RuntimeError("host refused the send")
            self.sent.append(data)
            if self.on_send is not None:
                self.on_send(data)
            return {"result": "ok"}
        raise AssertionError(f"unexpected Host action: {action}")


class _CaptureLogs(logging.Handler):
    """Capture the plugin's own log records so tests can inspect them."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def binding(installation: str, *, workspace: str = "workspace-1", revision: int = 1):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        placement_generation=1,
        runtime_revision=revision,
        artifact_digest="a" * 64,
    )


def build_plugin(**host_kwargs):
    plugin = sche_main.ScheNotify()
    host = FlatHost(**host_kwargs)
    plugin.plugin_runtime_handler = host
    return plugin, host


def _texts(payloads: list[dict]) -> list[str]:
    texts = []
    for payload in payloads:
        texts.append(
            "".join(
                part.get("text", "")
                for part in payload["message_chain"]
                if part.get("type") == "Plain"
            )
        )
    return texts


PAST = datetime.datetime(2020, 1, 1, 0, 0, 0)
FUTURE = datetime.datetime(2999, 1, 1, 0, 0, 0)


def test_schedule_is_per_installation():
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")

        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            await plugin.add_scheduled_event(
                time=PAST, message="A reminder", bot_uuid="bot", target_type="person", target_id="1"
            )
        with bind_invocation(host, config={"language": "zh_Hans"}, binding=second):
            await plugin.add_scheduled_event(
                time=PAST, message="B reminder", bot_uuid="bot", target_type="person", target_id="2"
            )

        with bind_invocation(host, config={"language": "zh_Hans"}, binding=second):
            # Pre-fix this returned ["A reminder", "B reminder"] from the shared list.
            assert [e["message"] for e in await plugin.get_scheduled_events()] == ["B reminder"]

        # A's scheduler fires A's reminder only; B's stays pending.
        await plugin._check_scheduled_events(plugin._scope(first))
        assert _texts(host.sent) == ["[Notify] A reminder"]
        with bind_invocation(host, config={"language": "zh_Hans"}, binding=second):
            assert [e["message"] for e in await plugin.get_scheduled_events()] == ["B reminder"]

        await plugin._check_scheduled_events(plugin._scope(second))
        assert _texts(host.sent) == ["[Notify] A reminder", "[Notify] B reminder"]

        # Nothing is left pending in either installation.
        assert plugin._events[plugin._scope(first)] == []
        assert plugin._events[plugin._scope(second)] == []

    asyncio.run(scenario())


def test_scheduler_is_registered_per_binding_and_stopped_on_revocation():
    async def scenario():
        plugin, host = build_plugin()
        first, second = binding("installation-a"), binding("installation-b")
        started: list[str] = []

        async def fake_loop(scope, *_authority):
            started.append(scope)
            await asyncio.sleep(3600)

        plugin._check_loop_wrapper = fake_loop

        with bind_invocation(host, config={}, binding=first):
            await plugin.add_scheduled_event(
                time=FUTURE, message="A reminder", bot_uuid="bot", target_type="person", target_id="1"
            )
        with bind_invocation(host, config={}, binding=second):
            await plugin.add_scheduled_event(
                time=FUTURE, message="B reminder", bot_uuid="bot", target_type="person", target_id="2"
            )
        await asyncio.sleep(0)

        assert started == [plugin._scope(first), plugin._scope(second)]
        first_task = plugin._loops[plugin._scope(first)]

        await plugin.on_installation_revoked(first)
        assert first_task.cancelled() or first_task.done()
        assert plugin._scope(first) not in plugin._loops
        assert plugin._scope(first) not in plugin._events
        # A revoked installation's schedule is dropped: no late delivery.
        before = len(host.sent)
        await plugin._check_scheduled_events(plugin._scope(first))
        assert len(host.sent) == before
        # The sibling installation is untouched.
        assert plugin._scope(second) in plugin._loops
        assert [e["message"] for e in plugin._events[plugin._scope(second)]] == ["B reminder"]

        await plugin.on_installation_revoked(second)

    asyncio.run(scenario())


def test_detached_scheduler_reads_no_invocation_config():
    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")

        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            await plugin.add_scheduled_event(
                time=PAST, message="A reminder", bot_uuid="bot", target_type="person", target_id="1"
            )

        def refuse():
            raise AssertionError("detached scheduler read invocation config")

        plugin.get_config = refuse
        # Pre-fix _send_notification read self.get_config() on every delivery.
        await plugin._check_scheduled_events(plugin._scope(first))
        assert _texts(host.sent) == ["[Notify] A reminder"]

    asyncio.run(scenario())


def test_scope_key_is_the_full_binding():
    plugin, _host = build_plugin()
    assert plugin._scope(binding("installation-a")) == "instance-1:workspace-1:installation-a"
    assert plugin._scope(binding("installation-a")) != plugin._scope(binding("installation-a", workspace="workspace-2"))
    assert plugin._scope() == sche_main.LEGACY_SCOPE
    assert isinstance(plugin._scope(SimpleNamespace(instance_uuid="i", workspace_uuid="w", installation_uuid="x")), str)


def test_initialize_starts_no_scheduler():
    async def scenario():
        plugin, _host = build_plugin()
        await plugin.initialize()
        assert plugin._loops == {}

    asyncio.run(scenario())


def test_dedicated_binding_less_invocation_still_schedules():
    """A dedicated worker's invocation carries no binding; it keeps its own scope."""

    async def scenario():
        plugin, host = build_plugin()
        loop_scopes: list[str] = []

        async def fake_loop(scope, *_authority):
            loop_scopes.append(scope)
            await asyncio.sleep(3600)

        plugin._check_loop_wrapper = fake_loop
        with bind_invocation(host, config={"language": "en_US"}):
            await plugin.add_scheduled_event(
                time=PAST, message="dedicated", bot_uuid="bot", target_type="person", target_id="1"
            )
        await asyncio.sleep(0)
        assert loop_scopes == [sche_main.LEGACY_SCOPE]

        await plugin._check_scheduled_events(sche_main.LEGACY_SCOPE)
        assert _texts(host.sent) == ["[Notify] dedicated"]
        await plugin.on_installation_revoked(binding("installation-a"))
        assert plugin._loops  # a revoked binding does not disturb the legacy scope

    asyncio.run(scenario())


def _session(bot_uuid, launcher_type, launcher_id) -> Session:
    return Session(launcher_type=launcher_type, launcher_id=launcher_id, bot_uuid=bot_uuid)


def _context(bot_uuid, launcher_type, launcher_id, command, params=()) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=_session(bot_uuid, launcher_type, launcher_id),
        command_text=command,
        full_command_text=f"!{command}",
        command=command,
        crt_command=command,
        params=list(params),
        crt_params=list(params),
        privilege=0,
    )


async def _render(component, context) -> list[str]:
    return [ret.text async for ret in component._execute(context)]


def test_detached_send_runs_under_the_captured_installation_binding():
    """The background relay carries the scheduling installation's authority.

    Pre-fix the scheduler started its task in a fresh ``contextvars.Context()``
    and never re-entered an invocation, so the Host resolved the relay's binding
    to ``None`` (``host.authorities`` was ``[None]``) although the payload
    carried the tenant's reminder text and target.
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")

        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            await plugin.add_scheduled_event(
                time=PAST, message="A reminder", bot_uuid="bot", target_type="person", target_id="1"
            )

        # The scheduler is a real detached task: let it run its first pass.
        for _ in range(200):
            if host.sent:
                break
            await asyncio.sleep(0.01)

        assert _texts(host.sent) == ["[Notify] A reminder"]
        assert host.authorities == [first]
        assert plugin._events[plugin._scope(first)] == []

        # The authority belongs to the loop, so revocation withdraws it with it.
        await plugin.on_installation_revoked(first)
        assert plugin._loops == {}

    asyncio.run(scenario())


def test_session_key_distinguishes_bot_and_namespace():
    """Listing and deleting are keyed by the whole session, not by target id.

    Pre-fix ``get_scheduled_events(target_id)`` matched ``target_id`` only, so
    each of the three lookups below returned all three records, and a delete
    from one session removed another session's event.
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        scope = plugin._scope(first)
        with bind_invocation(host, config={}, binding=first):
            key_bot_a = ("bot-a", "person", "42")
            key_bot_b = ("bot-b", "person", "42")
            key_group = ("bot-a", "group", "42")
            assert len({key_bot_a, key_bot_b, key_group}) == 3

            for key, text in (
                (key_bot_a, "bot-a person"),
                (key_bot_b, "bot-b person"),
                (key_group, "group 42"),
            ):
                await plugin.add_scheduled_event(
                    time=FUTURE, message=text,
                    bot_uuid=key[0], target_type=key[1], target_id=key[2],
                )

            assert [e["message"] for e in await plugin.get_scheduled_events(key_bot_a)] == ["bot-a person"]
            assert [e["message"] for e in await plugin.get_scheduled_events(key_bot_b)] == ["bot-b person"]
            assert [e["message"] for e in await plugin.get_scheduled_events(key_group)] == ["group 42"]

            # A delete is refused when the event belongs to another session.
            other = (await plugin.get_scheduled_events(key_bot_b))[0]
            assert await plugin.delete_scheduled_event(other, key_bot_a) is False
            assert [e["message"] for e in await plugin.get_scheduled_events(key_bot_b)] == ["bot-b person"]
            assert await plugin.delete_scheduled_event(other, key_bot_b) is True
            assert await plugin.get_scheduled_events(key_bot_b) == []
            assert len(plugin._events[scope]) == 2

        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_session_key_is_the_trusted_triplet():
    """The key the commands build is ``(bot_uuid, target_type, target_id)``.

    Pre-fix this API did not exist; the commands filtered by ``target_id``.
    """
    plugin, _host = build_plugin()
    assert plugin.session_key("bot-a", "person", "42") == ("bot-a", "person", "42")
    assert plugin.session_key("bot-a", "group", "42") != plugin.session_key("bot-a", "person", "42")
    assert plugin.session_key(None, "person", 42) == ("", "person", "42")


def test_schedule_commands_do_not_reach_another_session():
    """``!sche`` / ``!dsche`` act on the current trusted session only.

    Both sessions belong to one installation and share launcher id "42" but use
    different bots. Pre-fix ``!sche`` listed ("A reminder", "B reminder") and
    ``!dsche i 1`` deleted the *other* bot's reminder.
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        sche, dsche = ScheCommand(), DscheCommand()
        for component in (sche, dsche):
            component.plugin = plugin

        key_a = ("bot-a", "person", "42")
        key_b = ("bot-b", "person", "42")
        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            for key, text in ((key_a, "A reminder"), (key_b, "B reminder")):
                await plugin.add_scheduled_event(
                    time=FUTURE, message=text,
                    bot_uuid=key[0], target_type=key[1], target_id=key[2],
                )

            listed_b = (await _render(sche, _context("bot-b", LauncherTypes.PERSON, "42", "sche")))[0]
            assert "B reminder" in listed_b
            assert "A reminder" not in listed_b

            deleted_b = (
                await _render(
                    dsche, _context("bot-b", LauncherTypes.PERSON, "42", "dsche", ("i", "1"))
                )
            )[0]
            assert "B reminder" in deleted_b
            assert [e["message"] for e in await plugin.get_scheduled_events(key_a)] == ["A reminder"]
            assert await plugin.get_scheduled_events(key_b) == []

        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_tool_schedules_under_the_sessions_own_identity():
    """The Tool stores the session's bot uuid together with type and id.

    Pre-fix the reminder could only be found by ``target_id``, so a lookup by the
    full identity returned nothing (the plugin had no such key).
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        tool = ScheduleNotify()
        tool.plugin = plugin

        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            result = await tool.call(
                {"time_str": "2999-01-01 00:00:00", "message": "from bot-a"},
                _session("bot-a", LauncherTypes.PERSON, "42"),
                1,
            )
            assert "from bot-a" in result
            assert [
                e["message"] for e in await plugin.get_scheduled_events(("bot-a", "person", "42"))
            ] == ["from bot-a"]
            assert await plugin.get_scheduled_events(("bot-b", "person", "42")) == []

        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_failed_delivery_keeps_the_reminder_queued():
    """A refused Host send must not delete the reminder.

    Pre-fix ``_send_notification`` swallowed the failure and the loop removed the
    event anyway, so ``plugin._events[scope]`` was empty and the reminder was
    lost forever.
    """

    async def scenario():
        plugin, host = build_plugin(fail_sends=1)
        first = binding("installation-a")
        scope = plugin._scope(first)

        with bind_invocation(host, config={}, binding=first):
            await plugin.add_scheduled_event(
                time=FUTURE, message="A reminder", bot_uuid="bot", target_type="person", target_id="1"
            )
        await plugin._stop_loop(scope)
        plugin._events[scope][0]["time"] = PAST

        await plugin._check_scheduled_events(scope)
        pending = plugin._events[scope]
        assert [e["message"] for e in pending] == ["A reminder"]
        assert pending[0]["failed_attempts"] == 1
        assert pending[0]["last_error"] == "host refused the send"

        # The next pass retries the still-pending reminder and delivers it.
        await plugin._check_scheduled_events(scope)
        assert plugin._events[scope] == []
        assert _texts(host.sent) == ["[Notify] A reminder"]

    asyncio.run(scenario())


def test_delivery_snapshot_survives_a_concurrent_delete():
    """A sibling invocation deleting an event mid-delivery must not break the loop.

    Pre-fix the loop iterated the live list and then called
    ``events.remove(event)`` for every due event it had sent; deleting one during
    the awaited send raised ``ValueError: list.remove(x): x not in list``.
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        scope = plugin._scope(first)

        def concurrent_delete(_payload):
            pending = plugin._events[scope]
            if len(host.sent) >= 2 and pending and pending[0]["message"] == "one":
                # What a sibling invocation's !dsche does while the loop awaits.
                del pending[0]

        host.on_send = concurrent_delete

        with bind_invocation(host, config={}, binding=first):
            for text in ("one", "two"):
                await plugin.add_scheduled_event(
                    time=FUTURE, message=text,
                    bot_uuid="bot", target_type="person", target_id="1",
                )
        await plugin._stop_loop(scope)
        for event in plugin._events[scope]:
            event["time"] = PAST

        await plugin._check_scheduled_events(scope)

        assert _texts(host.sent) == ["[Notify] one", "[Notify] two"]
        assert plugin._events[scope] == []

    asyncio.run(scenario())


def test_queue_is_bounded_and_reminder_text_is_not_logged():
    """The queue and stored text are bounded, and the queue is logged by size.

    Pre-fix the 101st reminder was accepted, the stored message was unbounded,
    and the debug line dumped the whole event dict (reminder text included).
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        scope = plugin._scope(first)
        limit = sche_main.MAX_EVENTS_PER_INSTALLATION

        records = _CaptureLogs()
        module_logger = logging.getLogger(sche_main.__name__)
        module_logger.addHandler(records)
        previous_level = module_logger.level
        module_logger.setLevel(logging.DEBUG)
        try:
            with bind_invocation(host, config={}, binding=first):
                for index in range(limit):
                    await plugin.add_scheduled_event(
                        time=FUTURE, message=f"reminder {index}",
                        bot_uuid="bot", target_type="person", target_id="1",
                    )
                assert await plugin.add_scheduled_event(
                    time=FUTURE, message="overflow",
                    bot_uuid="bot", target_type="person", target_id="1",
                ) is False
                assert len(plugin._events[scope]) == limit

                await plugin.delete_scheduled_event(plugin._events[scope][0])
                assert await plugin.add_scheduled_event(
                    time=FUTURE, message="x" * (sche_main.MAX_MESSAGE_LENGTH + 500),
                    bot_uuid="bot", target_type="person", target_id="1",
                ) is True
                assert len(plugin._events[scope][-1]["message"]) == sche_main.MAX_MESSAGE_LENGTH

            await plugin._stop_loop(scope)
            await plugin._check_scheduled_events(scope)
        finally:
            module_logger.removeHandler(records)
            module_logger.setLevel(previous_level)

        assert not [message for message in records.messages if "reminder 0" in message]
        assert [message for message in records.messages if "pending events" in message]

        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_worker_upgrade_restarts_the_loop_under_the_new_binding():
    """A worker upgrade keeps the scope token but must replace the authority.

    The scope excludes ``runtime_revision``, so an upgraded installation reuses
    the same token. Pre-fix ``_ensure_loop`` returned while the superseded task
    was alive, so the post-upgrade reminder would have been delivered (or not
    delivered at all) by the loop holding the old revision's binding.
    """

    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        scope = plugin._scope(first)

        with bind_invocation(host, config={}, binding=first):
            await plugin.add_scheduled_event(
                time=FUTURE, message="old revision", bot_uuid="bot", target_type="person", target_id="1"
            )
        await asyncio.sleep(0)
        superseded = plugin._loops[scope]

        revised = binding("installation-a", revision=2)
        assert plugin._scope(revised) == scope
        with bind_invocation(host, config={}, binding=revised):
            await plugin.add_scheduled_event(
                time=PAST, message="new revision", bot_uuid="bot", target_type="person", target_id="1"
            )
        await asyncio.sleep(0)

        assert plugin._loops[scope] is not superseded
        assert superseded.cancelled() or superseded.done()

        for _ in range(200):
            if host.sent:
                break
            await asyncio.sleep(0.01)
        assert _texts(host.sent) == ["[Notify] new revision"]
        assert host.authorities == [revised]

        await plugin.on_installation_revoked(revised)

    asyncio.run(scenario())
