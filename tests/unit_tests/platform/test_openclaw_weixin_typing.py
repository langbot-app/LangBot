import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.libs.openclaw_weixin_api.typing_indicator import TypingIndicator
from langbot.pkg.platform.processing_indicator import processing_indicator


def indicator():
    client = SimpleNamespace(
        get_config=AsyncMock(return_value=SimpleNamespace(ret=0, typing_ticket='ticket')),
        send_typing=AsyncMock(),
        stop_typing=AsyncMock(),
    )
    manager = TypingIndicator(client, lambda peer: 'context')
    manager.INTERVAL = 0.005
    return manager, client


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_keepalive_shared_lease_and_cached_ticket():
    manager, client = indicator()
    async with manager.processing('peer'):
        async with manager.processing('peer'):
            await until(lambda: client.send_typing.await_count >= 2)
            assert len(manager.leases) == 1
        client.stop_typing.assert_not_awaited()
    client.get_config.assert_awaited_once_with('peer', 'context')
    client.stop_typing.assert_awaited_once_with('peer', 'ticket')
    assert not manager.leases


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['error', 'cancel'])
async def test_processing_failure_stops_typing(failure):
    manager, client = indicator()

    async def work():
        async with manager.processing('peer'):
            await until(lambda: client.send_typing.await_count)
            if failure == 'error':
                raise ValueError('processing failed')
            await asyncio.Event().wait()

    task = asyncio.create_task(work())
    await until(lambda: client.send_typing.await_count)
    if failure == 'cancel':
        task.cancel()
    with pytest.raises(ValueError if failure == 'error' else asyncio.CancelledError):
        await task
    client.stop_typing.assert_awaited_once()
    assert not manager.leases


@pytest.mark.asyncio
async def test_ticket_failure_is_backed_off_without_interrupting_work():
    manager, client = indicator()
    client.get_config.side_effect = OSError('offline')
    async with manager.processing('peer'):
        await asyncio.sleep(0.03)
    client.get_config.assert_awaited_once()
    client.send_typing.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_and_peer_isolation():
    manager, client = indicator()
    async with manager.processing('one'), manager.processing('two'):
        await until(lambda: client.send_typing.await_count >= 2)
        await manager.close()
        assert client.stop_typing.await_count == 2
        count = client.send_typing.await_count
        async with manager.processing('three'):
            await asyncio.sleep(0.01)
        assert client.send_typing.await_count == count
    assert not manager.leases


@pytest.mark.asyncio
async def test_stop_refreshes_expired_ticket():
    manager, client = indicator()
    async with manager.processing('peer'):
        await until(lambda: client.send_typing.await_count)
        manager.cache['peer'] = ('old', 0, 600)
        client.get_config.return_value.typing_ticket = 'fresh'
    client.stop_typing.assert_awaited_once_with('peer', 'fresh')


@pytest.mark.asyncio
async def test_shutdown_does_not_cancel_stop_already_in_progress():
    manager, client = indicator()
    stopping = asyncio.Event()
    release = asyncio.Event()

    async def stop(*args):
        stopping.set()
        await release.wait()

    client.stop_typing.side_effect = stop

    async def work():
        async with manager.processing('peer'):
            await until(lambda: client.send_typing.await_count)

    task = asyncio.create_task(work())
    await asyncio.wait_for(stopping.wait(), 1)
    shutdown = asyncio.create_task(manager.close())
    await asyncio.sleep(0)
    assert not shutdown.done()
    release.set()
    await asyncio.wait_for(asyncio.gather(task, shutdown), 1)
    client.stop_typing.assert_awaited_once()
    assert not manager.leases


@pytest.mark.asyncio
async def test_optional_adapter_hook():
    async with processing_indicator(object(), 'person', 'peer'):
        pass
    from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinAdapter

    manager, client = indicator()
    adapter = OpenClawWeixinAdapter.model_construct(client=client)
    adapter._typing_indicator = manager
    async with processing_indicator(adapter, 'group', 'peer'):
        await asyncio.sleep(0)
    client.get_config.assert_not_awaited()
    async with processing_indicator(adapter, 'person', 'peer'):
        await until(lambda: client.send_typing.await_count)
    client.stop_typing.assert_awaited_once()
