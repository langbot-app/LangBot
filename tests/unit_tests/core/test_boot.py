from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.core import boot
from tools.regression.service_logs import records as parse_service_logs


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
async def test_main_signal_handler_handles_sigint_before_app_created(monkeypatch, caplog):
    captured_handler = {}
    # Signal handling must not touch a potentially blocked stdout stream.
    monkeypatch.setattr(boot, 'print', Mock(side_effect=AssertionError('stdout must not be used')), raising=False)

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    async def fake_make_app(loop):
        captured_handler[signal.SIGINT](signal.SIGINT, None)

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    with caplog.at_level(logging.ERROR, logger='langbot'):
        await boot.main(SimpleNamespace())

    assert caplog.records == []


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
async def test_main_reports_app_run_failure_and_still_shuts_down(monkeypatch, caplog, capsys):
    app_inst = SimpleNamespace(shutdown_called=False)

    async def shutdown():
        app_inst.shutdown_called = True

    async def run():
        raise RuntimeError('run failed')

    async def fake_make_app(loop):
        app_inst.shutdown = shutdown
        app_inst.run = run
        return app_inst

    monkeypatch.setattr(signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    with caplog.at_level(logging.ERROR, logger='langbot'):
        with pytest.raises(SystemExit) as exc_info:
            await boot.main(SimpleNamespace())

    assert exc_info.value.code == 1
    assert app_inst.shutdown_called is True
    assert capsys.readouterr().err == ''
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is not None
    assert str(caplog.records[0].exc_info[1]) == 'run failed'


@pytest.mark.asyncio
async def test_main_run_failure_and_shutdown_failure_preserves_exit_code_and_single_shutdown(
    monkeypatch, caplog, capsys
):
    shutdown_calls = 0

    async def shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        raise RuntimeError('shutdown failed')

    async def run():
        raise RuntimeError('run failed')

    async def fake_make_app(loop):
        return SimpleNamespace(run=run, shutdown=shutdown)

    monkeypatch.setattr(signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    with caplog.at_level(logging.ERROR, logger='langbot'):
        with pytest.raises(SystemExit) as exc_info:
            await boot.main(SimpleNamespace())

    assert exc_info.value.code == 1
    assert shutdown_calls == 1
    assert capsys.readouterr().err == ''
    assert len(caplog.records) == 2
    assert [record.levelno for record in caplog.records] == [logging.ERROR, logging.ERROR]
    assert [str(record.exc_info[1]) for record in caplog.records] == ['run failed', 'shutdown failed']


@pytest.mark.asyncio
async def test_main_signal_shutdown_failure_cancels_run_task_and_avoids_duplicate_shutdown(monkeypatch, caplog, capsys):
    import asyncio

    captured_handler = {}
    shutdown_calls = 0
    run_cancelled = False

    def fake_signal(sig, handler):
        captured_handler[sig] = handler

    async def shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        raise RuntimeError('signal shutdown failed')

    async def run():
        nonlocal run_cancelled
        captured_handler[signal.SIGINT](signal.SIGINT, None)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            run_cancelled = True
            raise

    async def fake_make_app(loop):
        return SimpleNamespace(run=run, shutdown=shutdown)

    monkeypatch.setattr(signal, 'signal', fake_signal)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    with caplog.at_level(logging.ERROR, logger='langbot'):
        with pytest.raises(SystemExit) as exc_info:
            await boot.main(SimpleNamespace())

    assert exc_info.value.code == 1
    assert shutdown_calls == 1
    assert run_cancelled is True
    assert capsys.readouterr().err == ''
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is not None
    assert str(caplog.records[0].exc_info[1]) == 'signal shutdown failed'


@pytest.mark.asyncio
async def test_main_normal_exit_shutdown_failure_logs_and_exits_nonzero(monkeypatch, caplog, capsys):
    shutdown_calls = 0

    async def shutdown():
        nonlocal shutdown_calls
        shutdown_calls += 1
        raise RuntimeError('cleanup failed')

    async def run():
        return None

    async def fake_make_app(loop):
        return SimpleNamespace(run=run, shutdown=shutdown)

    monkeypatch.setattr(signal, 'signal', lambda *_args: None)
    monkeypatch.setattr(boot, 'make_app', fake_make_app)

    with caplog.at_level(logging.ERROR, logger='langbot'):
        with pytest.raises(SystemExit) as exc_info:
            await boot.main(SimpleNamespace())

    assert exc_info.value.code == 1
    assert shutdown_calls == 1
    assert capsys.readouterr().err == ''
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.ERROR
    assert caplog.records[0].exc_info is not None
    assert str(caplog.records[0].exc_info[1]) == 'cleanup failed'


@pytest.mark.parametrize('after_logger_setup', [False, True], ids=['before-logger-setup', 'after-logger-setup'])
def test_main_logs_single_leveled_traceback_before_and_after_logger_setup(tmp_path, after_logger_setup):
    script = textwrap.dedent("""\
        import asyncio
        import os
        from pathlib import Path
        from types import SimpleNamespace

        from langbot.pkg.core import boot
        from langbot.pkg.core.bootutils import log as logmod

        Path('data/logs').mkdir(parents=True, exist_ok=True)
        logmod.LOG_DIR = str(Path('data/logs'))

        class FakeApp:
            def __init__(self):
                self.event_loop = None
                self.logger = None
                self.log_cache = None

            async def initialize(self):
                pass

            async def shutdown(self):
                Path('cleaned.txt').write_text('ok', encoding='utf-8')

        class FailingStage:
            async def run(self, ap):
                raise RuntimeError('boot boom')

        boot.app.Application = FakeApp
        boot.stage.preregistered_stages['FailingStage'] = FailingStage
        if os.environ['AFTER_LOGGER_SETUP'] == '1':
            boot.stage_order = ['SetupLoggerStage', 'FailingStage']
        else:
            boot.stage_order = ['FailingStage']

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(boot.main(loop))
        finally:
            loop.close()
    """)
    env = dict(
        os.environ,
        PYTHONPATH=str(Path(boot.__file__).resolve().parents[3]),
        PYTHONIOENCODING='utf-8',
        AFTER_LOGGER_SETUP=str(int(after_logger_setup)),
        NO_COLOR='1',
    )
    proc = subprocess.run(
        [sys.executable, '-c', script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert proc.returncode == 1
    assert (tmp_path / 'cleaned.txt').read_text(encoding='utf-8') == 'ok'

    combined = proc.stdout + proc.stderr
    assert combined.count('Traceback (most recent call last):') == 1, combined

    parsed = list(parse_service_logs(combined.splitlines(), 'core'))
    error_records = [rec for rec in parsed if rec.level == 'ERROR']
    assert len(error_records) == 1, parsed
    record = error_records[0]
    assert record.service == 'core'
    assert 'LangBot core failed' in record.msg
    assert 'RuntimeError: boot boom' in record.msg
    assert any('Traceback (most recent call last):' in line for line in record.continuation)
    assert any('RuntimeError: boot boom' in line for line in record.continuation)

    if after_logger_setup:
        wf_files = list((tmp_path / 'data/logs').glob('*.log.wf'))
        assert len(wf_files) == 1
        wf_text = wf_files[0].read_text(encoding='utf-8')
        assert 'ERROR [CORE.BOOT]' in wf_text
        assert 'RuntimeError: boot boom' in wf_text
