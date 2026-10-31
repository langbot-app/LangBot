"""Exercise actual installed SDK RPC cancellation, not a mocked cancel contract."""

import asyncio
from types import SimpleNamespace

import pytest

from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.runtime.io.handler import ActionResponse
from tests.integration.plugin.test_rag_file_transfer_protocol import BINDING, protocol_stack


@pytest.mark.asyncio
@pytest.mark.parametrize('disconnect', [False, True], ids=['cancel-waiter', 'close-host-connection'])
async def test_b1_host_cancellation_does_not_fence_remote_ingest(tmp_path, monkeypatch, disconnect):
    async with protocol_stack(tmp_path, monkeypatch, 'shared', BINDING) as stack:
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
        vectors = set()
        selected = SimpleNamespace(_runtime_plugin_handler=stack.bridge)
        monkeypatch.setattr(stack.runtime.plugin_mgr, '_get_connected_rag_plugin', lambda *_: (selected, 'engine'))

        @stack.plugin.action(RuntimeToPluginAction.INGEST_DOCUMENT)
        async def ingest(data):
            entered.set()
            await release.wait()
            vectors.add('host-id')
            finished.set()
            return ActionResponse.success({'document_id': 'host-id', 'status': 'completed'})

        @stack.plugin.action(RuntimeToPluginAction.DELETE_DOCUMENT)
        async def delete(data):
            vectors.discard(data['document_id'])
            return ActionResponse.success({'success': True})

        async def send_ingest():
            with stack.core.installation_scope(BINDING):
                return await stack.core.rag_ingest_document('tester', 'engine', {})

        local = asyncio.create_task(send_ingest())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if disconnect:
                await stack.core.close()
                result = await asyncio.gather(local, return_exceptions=True)
                assert isinstance(result[0], Exception)
            else:
                local.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await local
            assert not finished.is_set()
            # The SDK has no ingest/delete barrier: a new caller can receive a
            # confirmed deletion while the old plugin action can still write.
            # Use the surviving Runtime->plugin connection after Host disconnect.
            result = await stack.bridge.rag_delete_document('kb-a', 'host-id')
            assert result == {'success': True}
            assert vectors == set()
            release.set()
            await asyncio.wait_for(finished.wait(), 5)
            assert vectors == {'host-id'}
        finally:
            release.set()
            if not local.done():
                local.cancel()
            await asyncio.gather(local, return_exceptions=True)
