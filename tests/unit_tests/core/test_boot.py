from __future__ import annotations

import signal
from types import SimpleNamespace

import pytest

from langbot.pkg.core import boot


@pytest.mark.asyncio
async def test_main_signal_handler_handles_sigint_before_app_created(monkeypatch):
    captured_handler = {}

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    async def fake_make_app(loop):
        captured_handler[signal.SIGINT](signal.SIGINT, None)

    def fake_exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)
    monkeypatch.setattr(boot.os, '_exit', fake_exit)

    with pytest.raises(SystemExit) as exc_info:
        await boot.main(SimpleNamespace())

    assert exc_info.value.code == 0


@pytest.mark.asyncio
async def test_main_signal_handler_disposes_created_app(monkeypatch):
    captured_handler = {}
    app_inst = SimpleNamespace(disposed=False)

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    def dispose():
        app_inst.disposed = True

    async def run():
        captured_handler[signal.SIGINT](signal.SIGINT, None)

    async def fake_make_app(loop):
        app_inst.dispose = dispose
        app_inst.run = run
        return app_inst

    def fake_exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)
    monkeypatch.setattr(boot.os, '_exit', fake_exit)

    with pytest.raises(SystemExit) as exc_info:
        await boot.main(SimpleNamespace())

    assert exc_info.value.code == 0
    assert app_inst.disposed is True
