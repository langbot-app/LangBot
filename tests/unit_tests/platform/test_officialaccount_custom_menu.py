from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from langbot.libs.official_account_api.menu_api import OfficialAccountAPIError
from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.platform.adapters.officialaccount import menu as custom_menu
from langbot.pkg.platform.adapters.officialaccount.adapter import OfficialAccountAdapter
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from tests.unit_tests.platform.test_officialaccount_eba_adapter import DummyLogger

TOKEN = 'webhook-token'

MENU = {
    'buttons': [
        {'id': 'site', 'name': '官网', 'type': 'view', 'url': 'https://langbot.app'},
        {
            'id': 'more',
            'name': '更多',
            'type': 'group',
            'sub_buttons': [
                {'id': 'hours', 'name': '营业时间', 'type': 'reply', 'text': '周一至周五 9:00-18:00'},
                {'id': 'ask', 'name': '问问 AI', 'type': 'ai', 'text': '介绍一下你们的产品'},
                {'id': 'order', 'name': '查订单', 'type': 'event', 'key': 'ORDER_QUERY'},
                {
                    'id': 'app',
                    'name': '小程序',
                    'type': 'miniprogram',
                    'appid': 'wx123',
                    'pagepath': 'pages/index',
                    'url': 'https://langbot.app',
                },
            ],
        },
    ]
}


def make_adapter(mode='drop', menu=MENU):
    return OfficialAccountAdapter(
        {
            'token': TOKEN,
            'EncodingAESKey': 'encoding-key',
            'AppID': 'app-id',
            'AppSecret': 'app-secret',
            'Mode': mode,
            'LoadingMessage': 'thinking',
            custom_menu.CONFIG_KEY: menu,
        },
        DummyLogger(),
    )


def click_request(key: str, user: str = 'openid-1', create_time: int = 1700000000):
    timestamp, nonce = str(create_time), 'n' + key
    signature = hashlib.sha1(''.join(sorted([TOKEN, timestamp, nonce])).encode()).hexdigest()
    body = (
        '<xml>'
        '<ToUserName><![CDATA[gh_bot]]></ToUserName>'
        f'<FromUserName><![CDATA[{user}]]></FromUserName>'
        f'<CreateTime>{create_time}</CreateTime>'
        '<MsgType><![CDATA[event]]></MsgType>'
        '<Event><![CDATA[CLICK]]></Event>'
        f'<EventKey><![CDATA[{key}]]></EventKey>'
        '</xml>'
    ).encode()

    async def data():
        return body

    return SimpleNamespace(
        method='POST',
        args={'signature': signature, 'timestamp': timestamp, 'nonce': nonce, 'echostr': '', 'msg_signature': ''},
        data=data(),
    )


def test_to_wechat_builds_menu_create_body():
    assert custom_menu.to_wechat(MENU) == {
        'button': [
            {'type': 'view', 'name': '官网', 'url': 'https://langbot.app'},
            {
                'name': '更多',
                'sub_button': [
                    {'type': 'click', 'name': '营业时间', 'key': 'lb:r:hours'},
                    {'type': 'click', 'name': '问问 AI', 'key': 'lb:a:ask'},
                    {'type': 'click', 'name': '查订单', 'key': 'ORDER_QUERY'},
                    {
                        'type': 'miniprogram',
                        'name': '小程序',
                        'url': 'https://langbot.app',
                        'appid': 'wx123',
                        'pagepath': 'pages/index',
                    },
                ],
            },
        ]
    }


@pytest.mark.parametrize(
    ('menu', 'message'),
    [
        ({'buttons': []}, 'at least one button'),
        ({'buttons': [{'id': str(i), 'name': 'a', 'type': 'view', 'url': 'https://a'} for i in range(4)]}, 'at most 3'),
        ({'buttons': [{'id': 'a', 'name': '一二三四五六', 'type': 'view', 'url': 'https://a'}]}, '16 bytes'),
        ({'buttons': [{'id': 'a', 'name': 'a', 'type': 'view', 'url': 'ftp://a'}]}, 'http'),
        ({'buttons': [{'id': 'a', 'name': 'a', 'type': 'reply', 'text': ' '}]}, 'text is required'),
        ({'buttons': [{'id': 'a', 'name': 'a', 'type': 'event', 'key': 'lb:x'}]}, 'must not start'),
        ({'buttons': [{'id': 'a', 'name': 'a', 'type': 'unsupported'}]}, 'unsupported button type'),
        (
            {
                'buttons': [
                    {'id': 'a', 'name': 'a', 'type': 'view', 'url': 'https://a'},
                    {'id': 'a', 'name': 'b', 'type': 'view', 'url': 'https://a'},
                ]
            },
            'duplicate',
        ),
        (
            {
                'buttons': [
                    {
                        'id': 'g',
                        'name': 'g',
                        'type': 'group',
                        'sub_buttons': [
                            {'id': str(i), 'name': 'a', 'type': 'view', 'url': 'https://a'} for i in range(6)
                        ],
                    }
                ]
            },
            'at most 5',
        ),
    ],
)
def test_to_wechat_rejects_invalid_menus(menu, message):
    with pytest.raises(custom_menu.MenuValidationError, match=message):
        custom_menu.to_wechat(menu)


def test_resolve_click_only_matches_langbot_buttons():
    assert custom_menu.resolve_click(MENU, 'lb:r:hours') == ('reply', '周一至周五 9:00-18:00')
    assert custom_menu.resolve_click(MENU, 'lb:a:ask') == ('ai', '介绍一下你们的产品')
    assert custom_menu.resolve_click(MENU, 'lb:r:ask') is None
    assert custom_menu.resolve_click(MENU, 'ORDER_QUERY') is None
    assert custom_menu.resolve_click(None, 'lb:r:hours') is None


def test_from_selfmenu_imports_web_console_menu():
    ids = iter(f'id{i}' for i in range(10))
    menu, warnings = custom_menu.from_selfmenu(
        {
            'is_menu_open': 1,
            'selfmenu_info': {
                'button': [
                    {'type': 'text', 'name': '联系我们', 'value': '电话 123'},
                    {
                        'name': '服务',
                        'sub_button': {
                            'list': [
                                {'type': 'view', 'name': '官网', 'url': 'https://langbot.app'},
                                {'type': 'news', 'name': '最新文章', 'value': 'media'},
                            ]
                        },
                    },
                ]
            },
        },
        lambda: next(ids),
    )
    assert menu == {
        'buttons': [
            {'id': 'id0', 'name': '联系我们', 'type': 'reply', 'text': '电话 123'},
            {
                'id': 'id1',
                'name': '服务',
                'type': 'group',
                'sub_buttons': [
                    {'id': 'id2', 'name': '官网', 'type': 'view', 'url': 'https://langbot.app'},
                    {'id': 'id3', 'name': '最新文章', 'type': 'unsupported', 'original_type': 'news'},
                ],
            },
        ]
    }
    assert warnings == ['buttons[1].sub_buttons[1]: button type news is not supported']


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['drop', 'passive', 'auto'])
async def test_fixed_reply_button_answers_inside_callback(mode):
    adapter = make_adapter(mode)
    listener = AsyncMock()
    adapter.register_listener(platform_events.EBAEvent, listener)

    response = await adapter.handle_unified_webhook('bot', '', click_request('lb:r:hours'))
    await asyncio.sleep(0)

    assert '<Content><![CDATA[周一至周五 9:00-18:00]]></Content>' in response
    assert '<ToUserName><![CDATA[openid-1]]></ToUserName>' in response
    listener.assert_not_awaited()


@pytest.mark.asyncio
async def test_ai_button_is_dispatched_as_text_message_and_reply_returns_in_callback():
    adapter = make_adapter('drop')
    received: list[platform_events.MessageReceivedEvent] = []

    async def on_event(event, _adapter):
        received.append(event)
        await adapter.reply_message(event, platform_message.MessageChain([platform_message.Plain(text='AI answer')]))

    adapter.register_listener(platform_events.MessageReceivedEvent, on_event)

    response = await adapter.handle_unified_webhook('bot', '', click_request('lb:a:ask'))

    assert len(received) == 1
    assert isinstance(received[0], platform_events.MessageReceivedEvent)
    assert str(received[0].message_chain) == '介绍一下你们的产品'
    assert '<Content><![CDATA[AI answer]]></Content>' in response


@pytest.mark.asyncio
async def test_custom_event_button_stays_platform_specific():
    adapter = make_adapter('drop')
    listener = AsyncMock()
    adapter.register_listener(platform_events.EBAEvent, listener)

    await adapter.handle_unified_webhook('bot', '', click_request('ORDER_QUERY'))

    event = listener.await_args.args[0]
    assert isinstance(event, platform_events.PlatformSpecificEvent)
    assert event.action == 'officialaccount.CLICK'
    assert event.data['EventKey'] == 'ORDER_QUERY'


def mock_http(monkeypatch, *, get=(), request=()):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = list(get)
    client.request.side_effect = list(request)
    factory = Mock(return_value=client)
    monkeypatch.setattr('langbot.libs.official_account_api.menu_api.httpx.AsyncClient', factory)
    monkeypatch.setattr('langbot.libs.official_account_api.customer_service.httpx.AsyncClient', factory)
    return client


@pytest.mark.asyncio
async def test_menu_publish_sends_utf8_body_with_shared_token(monkeypatch):
    adapter = make_adapter('auto')
    client = mock_http(
        monkeypatch,
        get=[httpx.Response(200, json={'access_token': 'token-1', 'expires_in': 7200})],
        request=[httpx.Response(200, json={'errcode': 0, 'errmsg': 'ok'})],
    )
    client.post.return_value = httpx.Response(200, json={'errcode': 0})

    result = await adapter.call_platform_api('menu.publish', {})
    # Customer-service sends reuse the cached token instead of requesting another one.
    await adapter.bot.customer_service.send('openid-1', 'hello')

    method, url = client.request.await_args.args
    kwargs = client.request.await_args.kwargs
    assert (method, url) == ('POST', 'https://api.weixin.qq.com/cgi-bin/menu/create')
    assert kwargs['params'] == {'access_token': 'token-1'}
    assert '营业时间'.encode() in kwargs['content']
    assert json.loads(kwargs['content']) == result['published'] == custom_menu.to_wechat(MENU)
    assert client.get.await_count == 1
    assert client.post.await_args.kwargs['params'] == {'access_token': 'token-1'}


@pytest.mark.asyncio
async def test_menu_get_treats_missing_menu_as_unpublished(monkeypatch):
    adapter = make_adapter()
    mock_http(
        monkeypatch,
        get=[httpx.Response(200, json={'access_token': 'token-1', 'expires_in': 7200})],
        request=[httpx.Response(200, json={'errcode': 46003, 'errmsg': 'menu no exist'})],
    )
    assert await adapter.call_platform_api('menu.get', {}) == {'saved': MENU, 'published': None}


@pytest.mark.asyncio
async def test_menu_api_errors_keep_wechat_errcode(monkeypatch):
    adapter = make_adapter()
    mock_http(
        monkeypatch,
        get=[httpx.Response(200, json={'access_token': 'token-1', 'expires_in': 7200})],
        request=[httpx.Response(200, json={'errcode': 48001, 'errmsg': 'api unauthorized'})],
    )
    with pytest.raises(OfficialAccountAPIError) as caught:
        await adapter.call_platform_api('menu.delete', {})
    assert (caught.value.errcode, caught.value.errmsg) == (48001, 'api unauthorized')


@pytest.mark.asyncio
async def test_menu_publish_validates_before_calling_wechat(monkeypatch):
    adapter = make_adapter(menu={'buttons': []})
    client = mock_http(monkeypatch)
    with pytest.raises(custom_menu.MenuValidationError):
        await adapter.call_platform_api('menu.publish', {})
    client.get.assert_not_awaited()


def make_bot_service(adapter, *, declared=('menu.publish',), enable=True):
    component = SimpleNamespace(
        metadata=SimpleNamespace(name='officialaccount-omni'),
        spec={'platform_specific_apis': [{'action': action} for action in declared]},
    )
    ap = SimpleNamespace(
        discover=SimpleNamespace(get_components_by_kind=lambda kind: [component]),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter))),
    )
    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot', 'adapter': 'officialaccount-omni', 'enable': enable})
    return service


@pytest.mark.asyncio
async def test_bot_service_rejects_undeclared_actions():
    adapter = SimpleNamespace(call_platform_api=AsyncMock())
    service = make_bot_service(adapter)
    with pytest.raises(ApplicationAPIException) as caught:
        await service.call_platform_api(None, 'bot', 'menu.delete', {})
    assert caught.value.error.code == 'platform_api_not_supported'
    adapter.call_platform_api.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_service_requires_enabled_bot():
    adapter = SimpleNamespace(call_platform_api=AsyncMock())
    with pytest.raises(ApplicationAPIException) as caught:
        await make_bot_service(adapter, enable=False).call_platform_api(None, 'bot', 'menu.publish', {})
    assert caught.value.error.code == 'bot_not_running'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('error', 'code', 'details'),
    [
        (
            OfficialAccountAPIError(40164, 'invalid ip'),
            'platform_api_error',
            {'errcode': 40164, 'errmsg': 'invalid ip'},
        ),
        (custom_menu.MenuValidationError('name is required', 'buttons[0]'), 'invalid_input', None),
    ],
)
async def test_bot_service_maps_adapter_errors(error, code, details):
    adapter = SimpleNamespace(call_platform_api=AsyncMock(side_effect=error))
    with pytest.raises(ApplicationAPIException) as caught:
        await make_bot_service(adapter).call_platform_api(None, 'bot', 'menu.publish', {})
    assert caught.value.error.code == code
    assert caught.value.error.details == details
