import asyncio
import threading

import pytest

from langbot.pkg.platform.sources.lark import NonBlockingLarkWSClient


@pytest.mark.asyncio
async def test_lark_connection_url_lookup_does_not_block_main_event_loop(monkeypatch):
    client = NonBlockingLarkWSClient('app-id', 'app-secret')
    lookup_started = threading.Event()
    release_lookup = threading.Event()
    base_connect_urls: list[str] = []

    def blocking_get_conn_url() -> str:
        lookup_started.set()
        if not release_lookup.wait(timeout=2):
            raise TimeoutError('test did not release the connection lookup')
        return 'wss://example.invalid/connect?device_id=device&service_id=service'

    async def fake_base_connect(self):
        base_connect_urls.append(self._get_conn_url())

    monkeypatch.setattr(client, '_get_conn_url', blocking_get_conn_url)
    monkeypatch.setattr('lark_oapi.ws.Client._connect', fake_base_connect)

    connect_task = asyncio.create_task(client._connect())
    await asyncio.wait_for(asyncio.to_thread(lookup_started.wait, 1), timeout=1)

    # If the SDK's synchronous requests.post still runs on the event-loop
    # thread, this sleep cannot complete until release_lookup is set.
    await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.1)
    assert not connect_task.done()

    release_lookup.set()
    await asyncio.wait_for(connect_task, timeout=1)

    assert base_connect_urls == ['wss://example.invalid/connect?device_id=device&service_id=service']
