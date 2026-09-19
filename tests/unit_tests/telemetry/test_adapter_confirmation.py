"""Real adapter acceptance must reflect confirmed operations, not normal returns."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain, Plain

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from langbot.pkg.telemetry import diagnostics as d


def make_adapter(version='4.11.0b3', **config):
    ap = SimpleNamespace(instance_config=SimpleNamespace(data={'space': {'url': 'https://example.invalid', **config}}))
    manager = d.DiagnosticsManager(ap, version=version, instance_id='instance-test')
    ap.diagnostics = manager
    context = ExecutionContext(instance_uuid=manager.instance_id, workspace_uuid=str(uuid4()), placement_generation=1)
    sdk = SimpleNamespace(edit_message_text=AsyncMock(return_value=True), send_message=AsyncMock(return_value=True))
    adapter = TelegramAdapter.model_construct(
        bot=sdk, config={'markdown_card': False}, logger=SimpleNamespace(ap=ap, execution_context=context), listeners={}
    )
    return adapter, manager, sdk


async def wire_events(manager):
    batches = []

    async def sender(request):
        batch = json.loads(request.content)
        batches.append(batch)
        return httpx.Response(
            200,
            json={
                'code': 200,
                'data': {'accepted_event_ids': [e['event_id'] for e in batch['events']], 'rejected': []},
            },
        )

    manager.client = httpx.AsyncClient(transport=httpx.MockTransport(sender))
    await manager.flush_once()
    assert not manager.pending
    await manager.shutdown(drain_timeout=0)
    assert 'PRIVATE_' not in json.dumps(batches)
    return [event for batch in batches for event in batch['events']]


def successes(events):
    return [e for e in events if e['attributes'].get('adapter_evidence') and e['outcome'] == 'succeeded']


@pytest.mark.asyncio
async def test_real_telegram_file_only_edit_is_not_acceptance_through_sender():
    adapter, manager, sdk = make_adapter()
    for _ in range(2):
        result = await adapter.edit_message(
            'person',
            'PRIVATE_CHAT',
            'PRIVATE_MESSAGE',
            MessageChain([File(name='PRIVATE_FILE', base64=base64.b64encode(b'PRIVATE_BYTES').decode())]),
        )
        assert result is None
    sdk.edit_message_text.assert_not_awaited()
    events = await wire_events(manager)
    assert len([e for e in events if e['operation'] == 'edit_message']) == 4
    assert not successes(events)


@pytest.mark.asyncio
async def test_real_telegram_acknowledged_void_edit_is_acceptance_through_sender():
    adapter, manager, sdk = make_adapter()
    assert (
        await adapter.edit_message(
            'person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE', MessageChain([Plain(text='PRIVATE_TEXT')])
        )
        is None
    )
    sdk.edit_message_text.assert_awaited_once_with(
        chat_id='PRIVATE_CHAT', message_id='PRIVATE_MESSAGE', text='PRIVATE_TEXT'
    )
    events = await wire_events(manager)
    assert len(successes(events)) == 1
    assert successes(events)[0]['attributes']['content_type'] == 'text'


@pytest.mark.asyncio
async def test_real_telegram_empty_send_is_not_acceptance():
    adapter, manager, sdk = make_adapter()
    assert await adapter.send_message('person', 'PRIVATE_CHAT', MessageChain([])) is None
    sdk.send_message.assert_not_awaited()
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_telegram_edit_exception_is_unchanged():
    adapter, manager, sdk = make_adapter()
    error = ValueError('PRIVATE_ERROR')
    sdk.edit_message_text.side_effect = error
    with pytest.raises(ValueError) as raised:
        await adapter.edit_message(
            'person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE', MessageChain([Plain(text='PRIVATE_TEXT')])
        )
    assert raised.value is error
    events = await wire_events(manager)
    assert not successes(events)
    assert any(e['outcome'] == 'failed' and e['operation'] == 'edit_message' for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'version,config',
    [('4.11.0', {}), ('4.11.0b3', {'disable_telemetry': True}), ('4.11.0b3', {'disable_beta_diagnostics': True})],
)
async def test_real_adapter_disabled_gates_keep_business_behavior(version, config):
    adapter, manager, sdk = make_adapter(version, **config)
    assert (
        await adapter.edit_message(
            'person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE', MessageChain([Plain(text='PRIVATE_TEXT')])
        )
        is None
    )
    sdk.edit_message_text.assert_awaited_once()
    assert await wire_events(manager) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [None, False, {}, {'queued': True}, {'stream': False}])
async def test_unconfirmed_normal_return_is_not_acceptance(result):
    adapter, manager, _ = make_adapter()

    async def call(self):
        return result

    call.__module__ = 'langbot.pkg.platform.adapters.telegram.adapter'
    observed = d.observe('api', 'send_message', source='platform', stage='accepted')(call)
    assert await observed(adapter) is result
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', [{}, {'results': []}, {'result': None}, {'queued': True}])
async def test_message_result_source_id_is_not_confirmation(raw):
    from langbot_plugin.api.entities.builtin.platform.events import MessageResult

    adapter, manager, _ = make_adapter()
    result = MessageResult(message_id='PRIVATE_SOURCE_ID', raw=raw)

    async def call(self):
        return result

    call.__module__ = 'langbot.pkg.platform.adapters.wecom.adapter'
    observed = d.observe('api', 'reply_message', source='platform', stage='accepted')(call)
    assert await observed(adapter) is result
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_discord_void_delete_is_confirmed():
    from langbot.pkg.platform.adapters.discord.adapter import DiscordAdapter

    adapter, manager, _ = make_adapter()
    message = SimpleNamespace(delete=AsyncMock(return_value=None))
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    discord = DiscordAdapter.model_construct(
        bot=SimpleNamespace(get_channel=lambda _: channel), logger=adapter.logger, config={}, listeners={}
    )
    assert await discord.delete_message('group', '123', '456') is None
    message.delete.assert_awaited_once()
    assert len(successes(await wire_events(manager))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [False, None])
async def test_real_telegram_unacknowledged_edit_keeps_void_return(result):
    adapter, manager, sdk = make_adapter()
    sdk.edit_message_text.return_value = result
    assert (
        await adapter.edit_message(
            'person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE', MessageChain([Plain(text='PRIVATE_TEXT')])
        )
        is None
    )
    sdk.edit_message_text.assert_awaited_once()
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_telegram_acknowledged_void_delete_is_acceptance():
    adapter, manager, sdk = make_adapter()
    sdk.delete_message = AsyncMock(return_value=True)
    assert await adapter.delete_message('person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE') is None
    sdk.delete_message.assert_awaited_once()
    assert len(successes(await wire_events(manager))) == 1


@pytest.mark.asyncio
async def test_real_telegram_sdk_message_send_is_acceptance():
    import datetime
    import telegram

    adapter, manager, sdk = make_adapter()
    sdk.send_message.return_value = telegram.Message(
        message_id=123, date=datetime.datetime.now(datetime.timezone.utc), chat=telegram.Chat(id=456, type='private')
    )
    assert await adapter.send_message('person', 'PRIVATE_CHAT', MessageChain([Plain(text='PRIVATE_TEXT')])) is None
    sdk.send_message.assert_awaited_once()
    assert len(successes(await wire_events(manager))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'raw', [{'ok': True, 'raw': None}, {'ok': True, 'raw': {'errcode': 42}}, {'results': [{'ok': True}, None]}]
)
async def test_wrapped_ack_does_not_hide_missing_or_failed_response(raw):
    adapter, manager, _ = make_adapter()

    async def call(self):
        return raw

    call.__module__ = 'langbot.pkg.platform.adapters.wecombot.adapter'
    observed = d.observe('api', 'reply_message', source='platform', stage='accepted')(call)
    assert await observed(adapter) is raw
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'action', ['check_tenant_access_token', 'refresh_app_access_token', 'refresh_tenant_access_token']
)
async def test_real_lark_self_app_token_noop_is_not_acceptance(action):
    from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter

    adapter, manager, _ = make_adapter()
    lark = LarkAdapter.model_construct(config={'app_type': 'self'}, logger=adapter.logger, listeners={})
    assert await lark.call_platform_api(action, {}) == {'ok': True}
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_telegram_mixed_edit_cannot_confirm_ignored_file():
    adapter, manager, sdk = make_adapter()
    message = MessageChain([Plain(text='PRIVATE_TEXT'), File(name='PRIVATE_FILE', base64='eA==')])
    assert await adapter.edit_message('person', 'PRIVATE_CHAT', 'PRIVATE_MESSAGE', message) is None
    sdk.edit_message_text.assert_awaited_once()
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_discord_sent_message_result_is_confirmed():
    from langbot.pkg.platform.adapters.discord.adapter import DiscordAdapter

    adapter, manager, _ = make_adapter()
    channel = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=123)))
    discord = DiscordAdapter.model_construct(
        bot=SimpleNamespace(get_channel=lambda _: channel), logger=adapter.logger, config={}, listeners={}
    )
    result = await discord.send_message('group', '456', MessageChain([Plain(text='PRIVATE_TEXT')]))
    assert result.message_id == 123
    channel.send.assert_awaited_once_with(content='PRIVATE_TEXT')
    assert len(successes(await wire_events(manager))) == 1


@pytest.mark.asyncio
async def test_real_aiocqhttp_empty_forward_is_not_acceptance():
    from langbot.pkg.platform.adapters.aiocqhttp.adapter import AiocqhttpAdapter
    from langbot_plugin.api.entities.builtin.platform.message import Forward

    adapter, manager, _ = make_adapter()
    sdk = SimpleNamespace(call_action=AsyncMock())
    onebot = AiocqhttpAdapter.model_construct(bot=sdk, logger=adapter.logger, config={}, listeners={})
    result = await onebot.send_message('group', '123', MessageChain([Forward(node_list=[])]))
    assert result.message_id is None and result.raw == {}
    sdk.call_action.assert_not_awaited()
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_telegram_unsupported_exception_is_unchanged():
    from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError

    adapter, manager, _ = make_adapter()
    with pytest.raises(NotSupportedError):
        await adapter.upload_file(b'PRIVATE_BYTES', 'PRIVATE_FILE')
    assert not successes(await wire_events(manager))


@pytest.mark.asyncio
async def test_real_lark_sent_message_result_is_confirmed():
    from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter

    adapter, manager, _ = make_adapter()
    create = AsyncMock(
        return_value=SimpleNamespace(success=lambda: True, data=SimpleNamespace(message_id='PRIVATE_SENT_ID'))
    )
    lark = LarkAdapter.model_construct(
        config={'app_type': 'self'},
        logger=adapter.logger,
        listeners={},
        api_client=SimpleNamespace(im=SimpleNamespace(v1=SimpleNamespace(message=SimpleNamespace(acreate=create)))),
    )
    result = await lark.send_message('group', 'PRIVATE_CHAT', MessageChain([Plain(text='PRIVATE_TEXT')]))
    assert result.message_id == 'PRIVATE_SENT_ID'
    create.assert_awaited_once()
    assert len(successes(await wire_events(manager))) == 1


@pytest.mark.asyncio
async def test_real_telegram_returned_user_info_is_confirmed():
    adapter, manager, sdk = make_adapter()
    sdk.get_chat = AsyncMock(return_value=SimpleNamespace(id=123, first_name='PRIVATE_NAME', username='PRIVATE_USER'))
    result = await adapter.get_user_info('PRIVATE_USER')
    assert result.id == 123
    sdk.get_chat.assert_awaited_once_with(chat_id='PRIVATE_USER')
    assert len(successes(await wire_events(manager))) == 1
