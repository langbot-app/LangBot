"""QWeather: per-installation config and a non-blocking async HTTP path."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from langbot_plugin.api.proxies.invocation import bind_invocation, current_config
from langbot_plugin.entities.io.context import InstallationBinding

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pkg.weather_data as weather_data  # noqa: E402


def _binding(installation: str, *, workspace: str = "workspace-qweather"):
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        installation_uuid=installation,
        runtime_revision=1,
        artifact_digest="b" * 64,
    )


class _StubPlugin:
    """Per-invocation config, exactly as the SDK's BasePlugin.get_config."""

    def __init__(self, handler):
        self.plugin_runtime_handler = handler

    def get_config(self) -> dict:
        return dict(current_config(self.plugin_runtime_handler) or {})

    def get_plugin_config(self) -> dict:
        return self.get_config()


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload


def _payload_for(url: str) -> dict:
    if "city/" in url:
        return {"code": "200", "location": [{"name": "Testville", "id": "101"}]}
    if "warning/now" in url:
        return {"code": "204"}
    if "air/now" in url:
        return {
            "code": "200",
            "now": {"category": "Good", "aqi": "50", "pm2p5": "12", "pm10": "20",
                    "o3": "30", "co": "0.5", "no2": "10", "so2": "5"},
        }
    if "weather/24h" in url:
        return {"code": "200", "hourly": [{"fxTime": "2026-01-01T00:00", "temp": "5", "icon": "100", "text": "Clear"}]}
    if "indices" in url:
        return {"code": "200", "daily": [{"name": "Sport", "category": "sport", "text": "Good"}]}
    if "astronomy/sun" in url:
        return {"code": "200", "sunrise": "06:00", "sunset": "18:00"}
    if url.endswith("/weather/now"):
        return {
            "code": "200",
            "now": {"obsTime": "2026-01-01T00:00+08:00", "temp": "15", "icon": "100",
                    "text": "Sunny", "windScale": "3", "windDir": "N", "humidity": "45",
                    "precip": "0", "vis": "10"},
        }
    return {"code": "200", "daily": [{"fxDate": "2026-01-01", "tempMax": "9", "tempMin": "1",
                                      "textDay": "Sunny", "textNight": "Clear",
                                      "iconDay": "100", "iconNight": "150"}]}


class _SlowHttp:
    """Async stand-in for ``httpx.AsyncClient``'s request (the network boundary)."""

    def __init__(self, delay: float):
        self.delay = delay
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        await asyncio.sleep(self.delay)
        return _FakeResponse(_payload_for(url))


class _ControlHttp:
    """Network stand-in with controllable failing and hanging branches.

    ``hang_suffixes`` maps a URL suffix to how long that request's cancellation
    teardown takes. The branch never completes on its own; only cancellation can
    end it.
    """

    def __init__(self, *, failing_suffix: str | None = None, hang_suffixes: dict[str, float] | None = None):
        self.failing_suffix = failing_suffix
        self.hang_suffixes = dict(hang_suffixes or {})
        self.hang_started = asyncio.Event()
        self.release = asyncio.Event()
        self.hang_tasks: dict[str, asyncio.Task] = {}
        self.tasks: list[asyncio.Task] = []

    async def wait_for_hangs(self, count: int, timeout: float = 1.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while len(self.hang_tasks) < count:
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError(f"only {len(self.hang_tasks)} of {count} hanging requests started")
            await asyncio.sleep(0.005)

    async def __call__(self, url, params=None):
        if "city/" not in url:
            self.tasks.append(asyncio.current_task())
        for suffix, cleanup in self.hang_suffixes.items():
            if url.endswith(suffix):
                self.hang_tasks[suffix] = asyncio.current_task()
                self.hang_started.set()
                try:
                    await self.release.wait()
                except asyncio.CancelledError:
                    # Cancellation still needs a teardown; a caller that returns
                    # before this finishes leaves a request task behind.
                    await asyncio.sleep(cleanup)
                    raise
        if self.failing_suffix is not None and url.endswith(self.failing_suffix):
            # Wait until a sibling request is provably in flight, then fail.
            await self.hang_started.wait()
            raise weather_data.APIError("upstream rejected the request")
        return _FakeResponse(_payload_for(url))


class WeatherSharedRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._original_get_data = weather_data._get_data

    def tearDown(self) -> None:
        weather_data._get_data = self._original_get_data

    async def _run_command(self, binding, config, slow: _SlowHttp, command, handler):
        weather_data._get_data = slow
        context = SimpleNamespace(crt_params=["Testville"])

        async def collect():
            return [
                item
                async for item in command.registered_subcommands["*"].subcommand(command, context)
            ]

        with bind_invocation(handler, config=config, binding=binding):
            task = asyncio.ensure_future(collect())
            ticks = 0
            while not task.done():
                await asyncio.sleep(0.02)
                ticks += 1
            results = await task
        return results, ticks

    async def test_handler_yields_the_loop_and_uses_the_invocation_config(self) -> None:
        from components.commands.weather import Weather as WeatherCommand

        binding_a = _binding("installation-qweather-a")
        binding_b = _binding("installation-qweather-b")
        slow = _SlowHttp(0.2)

        # ONE command object and one plugin serve both installations.
        handler = SimpleNamespace()
        command = WeatherCommand()
        command.plugin = _StubPlugin(handler)

        results_a, ticks_a = await self._run_command(
            binding_a, {"qweather_apikey": "KEY-A", "qweather_apitype": "0"}, slow, command, handler
        )
        results_b, ticks_b = await self._run_command(
            binding_b, {"qweather_apikey": "KEY-B", "qweather_apitype": "0"}, slow, command, handler
        )

        # The handler awaited the slow network boundary instead of holding the loop:
        # a concurrent 20 ms ticker kept running. Pre-fix the synchronous
        # requests.Session().get fan-out starved it and this stayed near zero.
        self.assertGreaterEqual(ticks_a, 5)
        self.assertGreaterEqual(ticks_b, 5)

        self.assertIn("温度", results_a[0].text)
        self.assertIsNone(results_a[0].error)

        keys_a = [params.get("key") for _, params in slow.calls[:8]]
        keys_b = [params.get("key") for _, params in slow.calls[8:]]
        self.assertEqual(keys_a, ["KEY-A"] * 8)
        self.assertEqual(keys_b, ["KEY-B"] * 8)
        self.assertNotIn("KEY-B", keys_a)
        self.assertNotIn("KEY-A", keys_b)

    async def test_failed_fan_out_leaves_no_request_task_running(self) -> None:
        """F-01: a failing branch must cancel and await its fan-out siblings.

        ``asyncio.gather`` propagates the first exception without cancelling the
        other tasks, so pre-fix the hanging request outlived the failed call
        while still holding this invocation's API key.
        """
        from pkg.weather_data import Weather as WeatherData

        http = _ControlHttp(failing_suffix="/indices/1d", hang_suffixes={"/astronomy/sun": 0.0})
        weather_data._get_data = http
        data = WeatherData(city_name="Testville", api_key="KEY-A", api_type=0)

        try:
            with self.assertRaises(weather_data.APIError):
                await data.load_data()

            hang_task = http.hang_tasks.get("/astronomy/sun")
            self.assertIsNotNone(hang_task, "the hanging sibling request never started")
            # The invocation is over (the error already propagated): no request
            # task may still be alive holding this call's API key.
            self.assertTrue(
                all(task.done() for task in http.tasks),
                "a request task outlived the failed load_data() call",
            )
            self.assertTrue(hang_task.cancelled())
        finally:
            for task in http.tasks:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_cancelled_invocation_leaves_no_request_task_running(self) -> None:
        """F-01 cancel path: cancellation must await the fan-out teardown.

        One sibling's teardown finishes immediately while the other's takes
        longer; returning before both complete would leave the slow request
        running after the invocation was cancelled.
        """
        from pkg.weather_data import Weather as WeatherData

        http = _ControlHttp(hang_suffixes={"/weather/now": 0.0, "/astronomy/sun": 0.2})
        weather_data._get_data = http
        data = WeatherData(city_name="Testville", api_key="KEY-A", api_type=0)

        loader = asyncio.ensure_future(data.load_data())
        try:
            await http.wait_for_hangs(2)
            loader.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await loader
            self.assertTrue(
                all(task.done() for task in http.tasks),
                "a request task outlived the cancelled load_data() call",
            )
            self.assertTrue(http.hang_tasks["/astronomy/sun"].cancelled())
        finally:
            if not loader.done():
                loader.cancel()
                await asyncio.gather(loader, return_exceptions=True)
            for task in http.tasks:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
