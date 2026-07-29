from __future__ import annotations

import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.core import boot


@pytest.mark.asyncio
async def test_make_app_shuts_down_partially_built_application(monkeypatch):
    app_inst = SimpleNamespace(
        event_loop=None,
        shutdown=AsyncMock(),
        initialize=AsyncMock(),
    )

    class FailingStage:
        async def run(self, ap):
            assert ap is app_inst
            raise RuntimeError('startup failed')

    monkeypatch.setattr(boot.app, 'Application', lambda: app_inst)
    monkeypatch.setattr(boot, 'stage_order', ['FailingStage'])
    monkeypatch.setitem(boot.stage.preregistered_stages, 'FailingStage', FailingStage)

    with pytest.raises(RuntimeError, match='startup failed'):
        await boot.make_app(SimpleNamespace())

    app_inst.shutdown.assert_awaited_once()
    app_inst.initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_signal_handler_handles_sigint_before_app_created(monkeypatch):
    captured_handler = {}

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    async def fake_make_app(loop):
        captured_handler[signal.SIGINT](signal.SIGINT, None)

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    await boot.main(SimpleNamespace())


@pytest.mark.asyncio
async def test_main_signal_handler_disposes_created_app(monkeypatch):
    captured_handler = {}
    app_inst = SimpleNamespace(shutdown_called=False)

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    async def shutdown():
        app_inst.shutdown_called = True

    async def run():
        captured_handler[signal.SIGINT](signal.SIGINT, None)

    async def fake_make_app(loop):
        app_inst.shutdown = shutdown
        app_inst.run = run
        return app_inst

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    await boot.main(SimpleNamespace())

    assert app_inst.shutdown_called is True


@pytest.mark.asyncio
async def test_main_reports_app_run_failure_and_still_shuts_down(monkeypatch):
    app_inst = SimpleNamespace(shutdown_called=False)

    async def shutdown():
        app_inst.shutdown_called = True

    async def run():
        raise RuntimeError('run failed')

    async def fake_make_app(loop):
        app_inst.shutdown = shutdown
        app_inst.run = run
        return app_inst

    print_exc = Mock()
    monkeypatch.setattr(signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)
    monkeypatch.setattr(boot.traceback, 'print_exc', print_exc)

    await boot.main(SimpleNamespace())

    print_exc.assert_called_once()
    assert app_inst.shutdown_called is True
