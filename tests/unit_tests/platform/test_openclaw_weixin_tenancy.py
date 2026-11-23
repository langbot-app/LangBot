import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources import openclaw_weixin
from langbot.pkg.platform.sources.openclaw_weixin import OpenClawWeixinAdapter


def make_adapter(*, execution_context: ExecutionContext | None):
    app = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        workspace_service=SimpleNamespace(
            get_execution_binding=AsyncMock(
                return_value=SimpleNamespace(
                    instance_uuid='instance-a',
                    workspace_uuid='workspace-a',
                    placement_generation=1,
                )
            )
        ),
    )
    logger = SimpleNamespace(
        ap=app,
        execution_context=execution_context,
        warning=AsyncMock(),
        info=AsyncMock(),
        error=AsyncMock(),
    )
    adapter = OpenClawWeixinAdapter.model_construct(
        config={'token': 'refreshed-token'},
        logger=logger,
        client=Mock(),
        bot_account_id='',
        listeners={},
        name='openclaw-weixin',
    )
    adapter._bot_uuid = 'shared-bot-uuid'
    return adapter, app, logger


@pytest.mark.asyncio
async def test_persist_config_scopes_duplicate_bot_uuid_to_workspace():
    adapter, app, _ = make_adapter(
        execution_context=ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
            bot_uuid='shared-bot-uuid',
        )
    )

    await adapter._persist_config()

    app.workspace_service.get_execution_binding.assert_awaited_once_with(
        'workspace-a',
        expected_generation=1,
    )
    statement = app.persistence_mgr.execute_async.await_args.args[0]
    params = statement.compile().params
    assert 'workspace-a' in params.values()
    assert 'shared-bot-uuid' in params.values()
    assert {'workspace_uuid', 'uuid'} <= {comparison.left.name for comparison in statement._where_criteria}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'execution_context',
    [
        None,
        ExecutionContext(
            instance_uuid='instance-a',
            workspace_uuid='workspace-a',
            placement_generation=1,
            bot_uuid='another-bot-uuid',
        ),
    ],
    ids=['missing-context', 'mismatched-bot'],
)
async def test_persist_config_fails_closed_without_matching_execution_context(execution_context):
    adapter, app, logger = make_adapter(execution_context=execution_context)

    await adapter._persist_config()

    app.persistence_mgr.execute_async.assert_not_awaited()
    logger.warning.assert_awaited_once()


@pytest.mark.asyncio
async def test_component_base64_decode_is_bounded(monkeypatch):
    monkeypatch.setattr(openclaw_weixin, '_MAX_OPENCLAW_COMPONENT_BYTES', 4)
    component = platform_message.File(base64='MTIzNDU=')

    with pytest.raises(ValueError, match='exceeds'):
        await OpenClawWeixinAdapter._get_component_bytes(component)


@pytest.mark.asyncio
async def test_component_base64_strips_data_uri_prefix():
    raw_payload = b'hello world audio payload'
    encoded = base64.b64encode(raw_payload).decode('ascii')
    component = platform_message.Voice(base64=f'data:audio/mpeg;base64,{encoded}')

    result = await OpenClawWeixinAdapter._get_component_bytes(component)
    assert result == raw_payload


@pytest.mark.asyncio
async def test_voice_send_gracefully_degrades_to_file_when_silk_unavailable(monkeypatch):
    adapter, app, logger = make_adapter(execution_context=None)
    adapter.client = AsyncMock()

    # Emulate SILK or ffmpeg unavailable
    monkeypatch.setattr('langbot.pkg.utils.audio.is_silk_available', lambda: False)
    monkeypatch.setattr('langbot.pkg.utils.audio.is_ffmpeg_available', lambda: False)

    raw_mp3 = b'ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x00fake-mp3-audio'
    encoded = base64.b64encode(raw_mp3).decode('ascii')
    voice_comp = platform_message.Voice(base64=f'data:audio/mpeg;base64,{encoded}', length=3)

    msg = platform_message.MessageChain([voice_comp])
    await adapter.send_message('friend', 'target-wxid', msg)

    # Should NOT call send_voice (which WeChat mobile would silently drop for MP3)
    adapter.client.send_voice.assert_not_awaited()
    # Should call send_file as graceful degradation
    adapter.client.send_file.assert_awaited_once_with(
        'target-wxid',
        raw_mp3,
        'voice.mp3',
        '',
    )

