"""The ``timezone`` config applies to every tool and command of ScheNotify.

Evidence model: the real SDK ``bind_invocation`` supplies the installation
config; the same plugin object serves two installations configured with
different timezones, and the scheduled instants are compared in UTC.
"""

from __future__ import annotations

import asyncio
import datetime
from zoneinfo import ZoneInfo

from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes
from langbot_plugin.api.proxies.invocation import bind_invocation

from test_installation_schedule import (
    _context,
    _render,
    _session,
    _texts,
    binding,
    build_plugin,
    sche_main,
)
from components.commands.dsche import DscheCommand
from components.commands.sche import ScheCommand
from components.tools.get_current_time_str import GetCurrentTimeStr
from components.tools.schedule_notify import ScheduleNotify

UTC = datetime.timezone.utc


def test_resolve_timezone_accepts_names_offsets_and_falls_back():
    resolve = sche_main.resolve_timezone
    assert resolve("Asia/Shanghai") == ZoneInfo("Asia/Shanghai")
    assert resolve(" UTC ") is UTC
    assert resolve("UTC+8") == datetime.timezone(datetime.timedelta(hours=8))
    assert resolve("GMT-03:30") == datetime.timezone(-datetime.timedelta(hours=3, minutes=30))
    assert resolve("+0530") == datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    # Empty or unknown: host local timezone (None), the pre-config behaviour.
    assert resolve("") is None
    assert resolve(None) is None
    assert resolve("Mars/Olympus") is None
    assert resolve("UTC+99") is None


def test_get_current_time_str_uses_the_configured_timezone():
    async def scenario():
        plugin, host = build_plugin()
        tool = GetCurrentTimeStr()
        tool.plugin = plugin
        with bind_invocation(host, config={"timezone": "Asia/Tokyo"}, binding=binding("a")):
            result = await tool.call({}, _session("bot", LauncherTypes.PERSON, "1"), 1)
        assert result.endswith("(Asia/Tokyo, UTC+09:00)")
        reported = datetime.datetime.strptime(result[:19], "%Y-%m-%d %H:%M:%S")
        expected = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).replace(tzinfo=None)
        assert abs((expected - reported).total_seconds()) < 5

    asyncio.run(scenario())


def test_schedule_notify_interprets_time_in_the_configured_timezone():
    """The same wall-clock string is a different instant per installation."""

    async def scenario():
        plugin, host = build_plugin()
        tool = ScheduleNotify()
        tool.plugin = plugin
        first, second = binding("installation-a"), binding("installation-b")
        session = _session("bot", LauncherTypes.PERSON, "1")

        with bind_invocation(host, config={"timezone": "Asia/Shanghai", "language": "en_US"}, binding=first):
            result = await tool.call({"time_str": "2999-01-01 08:00:00", "message": "a"}, session, 1)
            assert "2999-01-01 08:00:00 (Asia/Shanghai, UTC+08:00)" in result
            (event_a,) = await plugin.get_scheduled_events()
        with bind_invocation(host, config={"timezone": "UTC"}, binding=second):
            # A label copied from get_current_time_str is tolerated.
            await tool.call({"time_str": "2999-01-01 08:00:00 (UTC)", "message": "b"}, session, 1)
            (event_b,) = await plugin.get_scheduled_events()

        assert event_a["time"].astimezone(UTC) == datetime.datetime(2999, 1, 1, 0, 0, tzinfo=UTC)
        assert event_b["time"].astimezone(UTC) == datetime.datetime(2999, 1, 1, 8, 0, tzinfo=UTC)

        await plugin.on_installation_revoked(first)
        await plugin.on_installation_revoked(second)

    asyncio.run(scenario())


def test_past_check_uses_the_configured_timezone():
    """A wall-clock time that is future in UTC-12 but past in UTC+14."""

    async def scenario():
        plugin, host = build_plugin()
        tool = ScheduleNotify()
        tool.plugin = plugin
        session = _session("bot", LauncherTypes.PERSON, "1")
        # Current wall clock in UTC+2: already past in UTC+14, still ahead in UTC-12.
        wall = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
        time_str = wall.strftime("%Y-%m-%d %H:%M:%S")

        with bind_invocation(host, config={"timezone": "UTC+14", "language": "en_US"}, binding=binding("a")):
            assert await tool.call({"time_str": time_str, "message": "x"}, session, 1) == (
                "The scheduled time has already passed"
            )
        with bind_invocation(host, config={"timezone": "UTC-12", "language": "en_US"}, binding=binding("b")):
            assert "Scheduled successfully" in await tool.call(
                {"time_str": time_str, "message": "x"}, session, 1
            )
        await plugin.on_installation_revoked(binding("b"))

    asyncio.run(scenario())


def test_due_check_fires_by_instant_regardless_of_timezone():
    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        past = datetime.datetime.now(ZoneInfo("Pacific/Kiritimati")) - datetime.timedelta(minutes=1)
        future = datetime.datetime.now(ZoneInfo("Pacific/Pago_Pago")) + datetime.timedelta(hours=1)
        with bind_invocation(host, config={}, binding=first):
            for moment, text in ((past, "due"), (future, "later")):
                await plugin.add_scheduled_event(
                    time=moment, message=text, bot_uuid="bot", target_type="person", target_id="1"
                )
        await plugin._check_scheduled_events(plugin._scope(first))
        assert _texts(host.sent) == ["[Notify] due"]
        assert [e["message"] for e in plugin._events[plugin._scope(first)]] == ["later"]
        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())


def test_commands_display_times_in_the_configured_timezone():
    async def scenario():
        plugin, host = build_plugin()
        first = binding("installation-a")
        sche, dsche = ScheCommand(), DscheCommand()
        for component in (sche, dsche):
            component.plugin = plugin
        moment = datetime.datetime(2999, 1, 1, 0, 0, tzinfo=UTC)

        with bind_invocation(host, config={"language": "en_US"}, binding=first):
            await plugin.add_scheduled_event(
                time=moment, message="r", bot_uuid="bot", target_type="person", target_id="1"
            )
        with bind_invocation(host, config={"language": "en_US", "timezone": "America/New_York"}, binding=first):
            listed = (await _render(sche, _context("bot", LauncherTypes.PERSON, "1", "sche")))[0]
            assert "2998-12-31 19:00:00 (America/New_York, UTC-05:00)" in listed
        with bind_invocation(host, config={"language": "en_US", "timezone": "Asia/Kolkata"}, binding=first):
            deleted = (
                await _render(dsche, _context("bot", LauncherTypes.PERSON, "1", "dsche", ("i", "1")))
            )[0]
            assert "2999-01-01 05:30:00 (Asia/Kolkata, UTC+05:30)" in deleted
        await plugin.on_installation_revoked(first)

    asyncio.run(scenario())
