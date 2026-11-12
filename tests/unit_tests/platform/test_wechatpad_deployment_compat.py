import asyncio
import importlib
import sys
import threading
import time
import types
from functools import cache
from unittest.mock import AsyncMock, MagicMock, patch

from langbot.libs.wechatpad_api.api.friend import FriendApi
from langbot.libs.wechatpad_api.client import WeChatPadClient
from langbot.pkg.platform.sources import wechatpad_message_guard
from langbot.pkg.platform.sources.wechatpad_message_guard import (
    WeChatPadMessageDeduplicator,
    is_wechatpad_message,
)


@cache
def _load_wechatpad_adapter():
    module_name = 'langbot.pkg.platform.sources.wechatpad'
    if module_name not in sys.modules:
        logger_module = types.ModuleType('langbot.pkg.platform.logger')
        logger_module.EventLogger = object
        with patch.dict(sys.modules, {'langbot.pkg.platform.logger': logger_module}):
            module = importlib.import_module(module_name)
        return module.WeChatPadAdapter

    return sys.modules[module_name].WeChatPadAdapter


def _build_adapter(*, auto_accept_friend: bool = False):
    adapter_class = _load_wechatpad_adapter()
    config = {
        'wechatpad_url': 'http://wechatpad.invalid',
        'wechatpad_ws': 'ws://wechatpad.invalid',
        'admin_key': '',
        'token': 'test-token',
        'wxid': 'wxid_bot',
        'auto_accept_friend': auto_accept_friend,
    }
    return adapter_class(config, AsyncMock())


def test_same_new_msg_id_is_seen_only_once():
    deduplicator = WeChatPadMessageDeduplicator()
    event = {'new_msg_id': 123, 'from_user_name': {'str': 'wxid_sender'}}

    assert deduplicator.is_duplicate(event) is False
    assert deduplicator.is_duplicate(event) is True


def test_same_content_with_different_message_ids_is_not_deduplicated():
    deduplicator = WeChatPadMessageDeduplicator()

    first = {'new_msg_id': 123, 'content': {'str': '相同内容'}}
    second = {'new_msg_id': 456, 'content': {'str': '相同内容'}}

    assert deduplicator.is_duplicate(first) is False
    assert deduplicator.is_duplicate(second) is False


def test_non_message_event_is_ignored():
    assert is_wechatpad_message({'Type': 10000, 'loginState': 1}) is False
    assert is_wechatpad_message({'from_user_name': {'str': 'wxid_sender'}}) is True


def test_only_text_messages_are_accepted():
    event = {'from_user_name': {'str': 'wxid_sender'}}

    assert wechatpad_message_guard.is_wechatpad_text_message({**event, 'msg_type': 1}) is True
    assert wechatpad_message_guard.is_wechatpad_text_message({**event, 'msg_type': 3}) is False
    assert wechatpad_message_guard.is_wechatpad_text_message({**event, 'msg_type': 34}) is False
    assert wechatpad_message_guard.is_wechatpad_text_message({**event, 'msg_type': 49}) is False
    assert wechatpad_message_guard.is_wechatpad_text_message(event) is False


def test_only_type_37_messages_are_friend_requests():
    event = {'from_user_name': {'str': 'fmessage'}}

    assert wechatpad_message_guard.is_wechatpad_friend_request({**event, 'msg_type': 37}) is True
    assert wechatpad_message_guard.is_wechatpad_friend_request({**event, 'msg_type': 1}) is False
    assert wechatpad_message_guard.is_wechatpad_friend_request(event) is False


def test_friend_api_accepts_request_with_wechatpad_contract():
    api = FriendApi('http://wechatpad.invalid', 'test-token')

    with patch('langbot.libs.wechatpad_api.api.friend.post_json') as post_json:
        post_json.return_value = {'Code': 200}
        result = api.accept_friend_request(
            scene=30,
            v3='v3_requester@stranger',
            v4='v4_ticket',
        )

    assert result == {'Code': 200}
    post_json.assert_called_once_with(
        base_url='http://wechatpad.invalid/friend/AgreeAdd',
        token='test-token',
        data={
            'ChatRoomUserName': '',
            'OpCode': 3,
            'Scene': 30,
            'V3': 'v3_requester@stranger',
            'V4': 'v4_ticket',
            'VerifyContent': '',
        },
    )


def test_friend_api_passes_chatroom_context_for_group_request():
    api = FriendApi('http://wechatpad.invalid', 'test-token')

    with patch('langbot.libs.wechatpad_api.api.friend.post_json') as post_json:
        post_json.return_value = {'Code': 200}
        result = api.accept_friend_request(
            scene=14,
            v3='v3_requester@stranger',
            v4='v4_ticket',
            chatroom_username='room@chatroom',
        )

    assert result == {'Code': 200}
    post_json.assert_called_once_with(
        base_url='http://wechatpad.invalid/friend/AgreeAdd',
        token='test-token',
        data={
            'ChatRoomUserName': 'room@chatroom',
            'OpCode': 3,
            'Scene': 14,
            'V3': 'v3_requester@stranger',
            'V4': 'v4_ticket',
            'VerifyContent': '',
        },
    )


def test_wechatpad_client_exposes_friend_request_acceptance():
    client = WeChatPadClient('http://wechatpad.invalid', 'test-token')
    client._friend_api.accept_friend_request = MagicMock(return_value={'Code': 200})

    result = client.accept_friend_request(
        scene=14,
        v3='v3_requester@stranger',
        v4='v4_ticket',
        chatroom_username='room@chatroom',
    )

    assert result == {'Code': 200}
    client._friend_api.accept_friend_request.assert_called_once_with(
        scene=14,
        v3='v3_requester@stranger',
        v4='v4_ticket',
        chatroom_username='room@chatroom',
    )


def test_friend_request_is_ignored_when_auto_accept_is_disabled():
    async def scenario():
        adapter = _build_adapter(auto_accept_friend=False)
        adapter.bot.accept_friend_request = MagicMock(return_value={'Code': 200})

        result = await adapter.ws_message(
            {
                'from_user_name': {'str': 'fmessage'},
                'msg_type': 37,
                'new_msg_id': 123,
                'content': {'str': '<msg encryptusername="v3_requester@stranger" ticket="v4_ticket" scene="30" />'},
            }
        )

        assert result == 'ok'
        adapter.bot.accept_friend_request.assert_not_called()

    asyncio.run(scenario())


def test_friend_request_is_accepted_once_when_auto_accept_is_enabled():
    async def scenario():
        adapter = _build_adapter(auto_accept_friend=True)
        adapter.bot.accept_friend_request = MagicMock(return_value={'Code': 200})
        payload = {
            'from_user_name': {'str': 'fmessage'},
            'msg_type': 37,
            'new_msg_id': 123,
            'content': {
                'str': '<msg encryptusername="v3_requester@stranger" ticket="v4_ticket" '
                'scene="14" chatroomusername="room@chatroom" />'
            },
        }

        assert await adapter.ws_message(payload) == 'ok'
        assert await adapter.ws_message(payload) == 'ok'

        adapter.bot.accept_friend_request.assert_called_once_with(
            scene=14,
            v3='v3_requester@stranger',
            v4='v4_ticket',
            chatroom_username='room@chatroom',
        )
        adapter.logger.info.assert_awaited_once()

    asyncio.run(scenario())


def test_friend_request_uses_fromusername_as_v3_fallback():
    async def scenario():
        adapter = _build_adapter(auto_accept_friend=True)
        adapter.bot.accept_friend_request = MagicMock(return_value={'Code': 200})

        result = await adapter.ws_message(
            {
                'from_user_name': {'str': 'fmessage'},
                'msg_type': 37,
                'new_msg_id': 123,
                'content': {'str': '<msg fromusername="v3_requester@stranger" ticket="v4_ticket" scene="30" />'},
            }
        )

        assert result == 'ok'
        adapter.bot.accept_friend_request.assert_called_once_with(
            scene=30,
            v3='v3_requester@stranger',
            v4='v4_ticket',
            chatroom_username='',
        )

    asyncio.run(scenario())


def test_friend_request_with_failed_business_response_is_logged_as_error():
    async def scenario():
        adapter = _build_adapter(auto_accept_friend=True)
        adapter.bot.accept_friend_request = MagicMock(
            return_value={'Code': 200, 'Data': {'base_response': {'ret': -24}}}
        )

        result = await adapter.ws_message(
            {
                'from_user_name': {'str': 'fmessage'},
                'msg_type': 37,
                'new_msg_id': 123,
                'content': {
                    'str': '<msg encryptusername="v3_requester@stranger" ticket="v4_ticket" '
                    'scene="14" chatroomusername="room@chatroom" />'
                },
            }
        )

        assert result == 'ok'
        adapter.logger.error.assert_awaited_once()
        adapter.logger.info.assert_not_awaited()

    asyncio.run(scenario())


def test_malformed_friend_request_is_logged_and_does_not_call_api():
    async def scenario():
        adapter = _build_adapter(auto_accept_friend=True)
        adapter.bot.accept_friend_request = MagicMock(return_value={'Code': 200})

        result = await adapter.ws_message(
            {
                'from_user_name': {'str': 'fmessage'},
                'msg_type': 37,
                'new_msg_id': 123,
                'content': {'str': '<msg'},
            }
        )

        assert result == 'ok'
        adapter.bot.accept_friend_request.assert_not_called()
        adapter.logger.error.assert_awaited_once()

    asyncio.run(scenario())


def test_non_text_messages_skip_conversion():
    async def scenario():
        adapter = _build_adapter()
        adapter.event_converter.target2yiri = AsyncMock(return_value=None)

        for index, msg_type in enumerate((3, 34, 49), start=1):
            result = await adapter.ws_message(
                {
                    'from_user_name': {'str': 'wxid_sender'},
                    'msg_type': msg_type,
                    'new_msg_id': index,
                }
            )
            assert result == 'ok'

        adapter.event_converter.target2yiri.assert_not_awaited()

    asyncio.run(scenario())


def test_text_message_is_converted_and_dispatched_once():
    async def scenario():
        adapter = _build_adapter()

        class TextEvent:
            pass

        event = TextEvent()
        listener = AsyncMock()
        adapter.event_converter.target2yiri = AsyncMock(return_value=event)
        adapter.listeners = {TextEvent: listener}
        payload = {
            'from_user_name': {'str': 'wxid_sender'},
            'msg_type': 1,
            'new_msg_id': 123,
        }

        assert await adapter.ws_message(payload) == 'ok'
        assert await adapter.ws_message(payload) == 'ok'

        adapter.event_converter.target2yiri.assert_awaited_once()
        listener.assert_awaited_once_with(event, adapter)

    asyncio.run(scenario())


def test_sync_envelope_submits_each_add_msg_to_main_loop():
    adapter = _build_adapter()
    submit_message = MagicMock()
    object.__setattr__(adapter, '_schedule_ws_message', submit_message)
    friend_request = {'msg_type': 37, 'new_msg_id': 123}
    text_message = {'msg_type': 1, 'new_msg_id': 456}

    adapter._schedule_ws_payload(
        {
            'Type': 10001,
            'AddMsgs': [friend_request, text_message],
        },
    )

    assert [call.args for call in submit_message.call_args_list] == [
        (friend_request,),
        (text_message,),
    ]


def test_single_websocket_message_is_submitted_unchanged():
    adapter = _build_adapter()
    submit_message = MagicMock()
    object.__setattr__(adapter, '_schedule_ws_message', submit_message)
    message = {'msg_type': 1, 'new_msg_id': 123}

    adapter._schedule_ws_payload(message)

    submit_message.assert_called_once_with(message)


def test_worker_thread_submits_message_to_main_event_loop_without_waiting():
    async def scenario():
        adapter = _build_adapter()
        main_loop = asyncio.get_running_loop()
        object.__setattr__(adapter, '_event_loop', main_loop)
        main_thread_id = threading.get_ident()
        listener_started = asyncio.Event()
        listener_release = asyncio.Event()
        listener_finished = asyncio.Event()
        execution_context = {}

        async def fake_ws_message(self, data):
            execution_context['loop'] = asyncio.get_running_loop()
            execution_context['thread_id'] = threading.get_ident()
            listener_started.set()
            await listener_release.wait()
            listener_finished.set()

        object.__setattr__(adapter, 'ws_message', types.MethodType(fake_ws_message, adapter))

        worker = threading.Thread(
            target=adapter._schedule_ws_message,
            args=({'msg_type': 1},),
        )
        worker.start()
        worker.join(timeout=0.2)

        assert worker.is_alive() is False
        await asyncio.wait_for(listener_started.wait(), timeout=1)
        assert execution_context == {
            'loop': main_loop,
            'thread_id': main_thread_id,
        }

        listener_release.set()
        await asyncio.wait_for(listener_finished.wait(), timeout=1)

    asyncio.run(scenario())


def test_main_loop_follow_up_task_is_not_cancelled_after_dispatch():
    async def scenario():
        adapter = _build_adapter()
        main_loop = asyncio.get_running_loop()
        object.__setattr__(adapter, '_event_loop', main_loop)
        follow_up_finished = asyncio.Event()

        async def fake_ws_message(self, data):
            async def follow_up():
                await asyncio.sleep(0.01)
                follow_up_finished.set()

            asyncio.create_task(follow_up())

        object.__setattr__(adapter, 'ws_message', types.MethodType(fake_ws_message, adapter))

        worker = threading.Thread(
            target=adapter._schedule_ws_message,
            args=({'msg_type': 1},),
        )
        worker.start()
        worker.join(timeout=0.2)

        assert worker.is_alive() is False
        await asyncio.wait_for(follow_up_finished.wait(), timeout=1)

    asyncio.run(scenario())


def test_outbound_send_does_not_block_main_event_loop():
    async def scenario():
        adapter = _build_adapter()
        adapter.message_converter.yiri2target = AsyncMock(return_value=[{'type': 'text', 'content': 'reply'}])
        release = threading.Event()

        def blocking_send(**kwargs):
            release.wait(timeout=1)
            return {'Code': 200}

        adapter.bot.send_text_message = blocking_send
        threading.Timer(0.2, release.set).start()

        started = time.monotonic()
        send_task = asyncio.create_task(adapter.send_message('person', 'wxid_target', object()))
        await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        elapsed = time.monotonic() - started

        assert elapsed < 0.15
        await send_task

    asyncio.run(scenario())
