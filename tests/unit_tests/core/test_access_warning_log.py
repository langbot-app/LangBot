import asyncio
import logging

import httpx
import pytest

from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.core.bootutils import log


@pytest.mark.asyncio
async def test_http_access_and_library_warnings_reach_wf(tmp_path, monkeypatch, unused_tcp_port):
    monkeypatch.setattr(log, 'LOG_DIR', str(tmp_path))
    server = HTTPController(None)

    @server.quart_app.get('/probe/<int:status>')
    async def probe(status):
        return '', status

    with (tmp_path / 'console').open('w') as console:
        monkeypatch.setattr(log.sys, 'stdout', console)
        await log.init_logging()
        stop = asyncio.Event()
        task = asyncio.create_task(server._run_task('127.0.0.1', unused_tcp_port, stop.wait))
        try:
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=4)) as client:
                for status in (200, 404, 500):
                    response = await client.get(f'http://127.0.0.1:{unused_tcp_port}/probe/{status}')
                    assert response.status_code == status
            logging.getLogger('library').warning('library warning')
        finally:
            stop.set()
            await task
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
                handler.close()
    text = next(tmp_path.glob('*.log.wf')).read_text()
    assert 'GET /probe/200' not in text
    assert any('WARN  [CORE.HTTP]' in line and 'GET /probe/404 1.1 404' in line for line in text.splitlines())
    assert any('ERROR [CORE.HTTP]' in line and 'GET /probe/500 1.1 500' in line for line in text.splitlines())
    assert '[CORE.LIBRARY]' in text
