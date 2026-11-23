"""Console backpressure must not stop request handling or process shutdown."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import threading
import time
import weakref

import pytest

from langbot.pkg.core.bootutils import log as logmod
from langbot.pkg.core.bootutils.log import NonBlockingConsoleHandler


def _logger(handler):
    logger = logging.Logger('console-test', logging.INFO)
    logger.addHandler(handler)
    return logger


def test_console_truncation_preserves_utf8_and_other_handlers(tmp_path):
    message = '界🙂' * logmod.CONSOLE_RECORD_MAX_BYTES
    with (tmp_path / 'console').open('w+b') as stream:
        handler = NonBlockingConsoleHandler(stream)
        logger = _logger(handler)
        other = logging.FileHandler(tmp_path / 'full.log', encoding='utf-8')
        logger.addHandler(other)
        try:
            logger.info('%s', message)
            handler.close()
            assert not handler._worker.is_alive()
            stream.seek(0)
            payload = stream.read()
            assert len(payload) <= logmod.CONSOLE_RECORD_MAX_BYTES
            assert payload.decode('utf-8').endswith('[console log truncated]\n')
            assert (tmp_path / 'full.log').read_text(encoding='utf-8') == message + '\n'
        finally:
            handler.close()
            other.close()


def test_close_with_full_queue_has_bounded_wait_and_reports_drops(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class StalledConsole(NonBlockingConsoleHandler):
        def _write(self, payload):
            entered.set()
            assert release.wait(5), 'test writer was not released'
            super()._write(payload)

    with (tmp_path / 'console').open('w+b') as stream:
        handler = StalledConsole(stream, capacity=2)
        logger = _logger(handler)
        try:
            logger.info('first')
            assert entered.wait(2)
            logger.info('second')
            logger.info('third')
            logger.info('overflow')
            assert handler.dropped_records == 1
            started = time.monotonic()
            handler.close()
            assert time.monotonic() - started < 1
            logger.info('after close')
            assert handler.dropped_records == 3
        finally:
            release.set()
            handler.close()
            handler._worker.join(timeout=2)
        assert not handler._worker.is_alive()
        stream.seek(0)
        output = stream.read().decode('utf-8')
        assert 'first\n' in output
        assert 'third\n' in output
        assert 'Console logging dropped 3 records' in output


def test_broken_console_does_not_write_errors_to_stderr(tmp_path, capsys):
    class BrokenConsole(NonBlockingConsoleHandler):
        def _write(self, payload):
            raise BrokenPipeError('reader exited')

    with (tmp_path / 'console').open('w+b') as stream:
        handler = BrokenConsole(stream)
        logger = _logger(handler)
        try:
            logger.info('first')
            assert handler._failed.wait(2)
            logger.info('second')
            handler._worker.join(timeout=2)
            assert handler.dropped_records == 2
            assert 'reader exited' in handler.write_error
            assert handler._queue.empty()
        finally:
            handler.close()
    assert capsys.readouterr().err == ''


def test_logging_shutdown_drains_healthy_console_without_handler_lock_deadlock(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class Console(NonBlockingConsoleHandler):
        def _write(self, payload):
            entered.set()
            assert release.wait(5), 'test writer was not released'
            super()._write(payload)

        def close(self):
            release.set()
            super().close()

    with (tmp_path / 'console').open('w+b') as stream:
        handler = Console(stream)
        logger = _logger(handler)
        try:
            logger.info('first')
            assert entered.wait(2)
            for index in range(20):
                logger.info('queued %d', index)
            # The standard shutdown holds handler.lock across flush and close.
            logging.shutdown([weakref.ref(handler)])
            assert not handler._worker.is_alive()
            assert handler.dropped_records == 0
            stream.seek(0)
            assert stream.read().decode('utf-8').splitlines() == ['first', *(f'queued {i}' for i in range(20))]
        finally:
            release.set()
            handler.close()
            handler._worker.join(timeout=2)


@pytest.mark.asyncio
async def test_reinitialization_closes_previous_handlers(tmp_path, monkeypatch):
    monkeypatch.setattr(logmod, 'LOG_DIR', str(tmp_path))
    with (tmp_path / 'console').open('w+b') as stream:
        monkeypatch.setattr(logmod.sys, 'stdout', stream)
        logger = await logmod.init_logging()
        previous = logger.handlers[:]
        try:
            logger.info('before reinitialization')
            await logmod.init_logging()
            logger.info('after reinitialization')
            assert len(logger.handlers) == 2
            assert all(handler._closed for handler in previous)
            assert not previous[0]._worker.is_alive()
            assert previous[1].stream is None
        finally:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
                handler.close()


@pytest.mark.parametrize('buffered_startup', [False, True], ids=['direct-init', 'buffered-entrypoint'])
def test_unread_stdout_keeps_webui_file_cache_and_process_exit_working(tmp_path, buffered_startup):
    # The parent deliberately never reads stdout until the child exits. This
    # exercises an actual full OS pipe, including interpreter finalization.
    script = textwrap.dedent("""\
        import asyncio
        import json
        import logging
        import os
        from pathlib import Path
        import sys
        import time
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from quart import Quart
        from langbot.pkg.core.bootutils import log
        from langbot.pkg.core.stages.setup_logger import PersistenceHandler
        from langbot.pkg.utils.logcache import LogCache

        async def main():
            Path('data/logs').mkdir(parents=True)
            cache = LogCache()
            logger = await log.init_logging([PersistenceHandler('cache', SimpleNamespace(log_cache=cache))])
            console = logger.handlers[0]
            app = Quart(__name__)

            @app.get('/health')
            async def health():
                logger.info('health request completed')
                return {'ok': True}

            async def produce():
                for index in range(800):
                    logger.info('record %d %s', index, 'x' * 2048)
                    if index % 16 == 0:
                        await asyncio.sleep(0)

            producer = asyncio.create_task(produce())
            await producer
            response = await app.test_client().get('/health')
            assert response.status_code == 200
            assert await response.get_json() == {'ok': True}
            assert console.dropped_records > 0
            with console._queue.mutex:
                queued = list(console._queue.queue)
            assert len(queued) <= log.CONSOLE_QUEUE_CAPACITY
            assert all(isinstance(item, bytes) and len(item) <= log.CONSOLE_RECORD_MAX_BYTES for item in queued)
            assert 'health request completed' in cache.get_log_by_pointer(0, 0)[0]
            assert any('health request completed' in path.read_text(encoding='utf-8')
                       for path in Path('data/logs').glob('*.log'))
            started = time.monotonic()
            logging.shutdown()
            assert time.monotonic() - started < 1
            Path('result.json').write_text(json.dumps({'dropped': console.dropped_records}), encoding='utf-8')

        if os.environ['LANGBOT_TEST_BUFFERED_STARTUP'] == '1':
            from langbot import __main__ as entrypoint
            from langbot.pkg.core import boot
            from langbot.pkg.core.bootutils import deps, files

            # Run the actual entrypoint's banner print without starting bots,
            # installing dependencies, or loading a real configuration.
            assert not sys.stdout.line_buffering
            assert not sys.stdout.write_through
            deps.check_deps = AsyncMock(return_value=[])
            files.generate_files = AsyncMock(return_value=[])

            async def run_after_startup(loop):
                await main()

            boot.main = run_after_startup
            entrypoint.main()
        else:
            asyncio.run(main())
    """)
    env = dict(
        os.environ,
        PYTHONPATH=str(Path(logmod.__file__).resolve().parents[4]),
        PYTHONIOENCODING='utf-8',
        LANGBOT_TEST_BUFFERED_STARTUP=str(int(buffered_startup)),
    )
    env.pop('PYTHONUNBUFFERED', None)
    with subprocess.Popen(
        [sys.executable, '-c', script],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
            pytest.fail(f'Logging or process exit blocked on stdout: {stderr.decode(errors="replace")}')
        _, stderr = process.communicate()
        assert process.returncode == 0, stderr.decode(errors='replace')
    assert (tmp_path / 'result.json').exists()
