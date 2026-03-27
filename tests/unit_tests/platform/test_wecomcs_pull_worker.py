import pytest

from langbot.libs.wecom_customer_service_api.api import WecomCSInvalidSyncMsgTokenError
from langbot.pkg.platform.wecomcs.pull_worker import PullLockNotAcquiredError, WecomCSPullWorker
from langbot.pkg.platform.wecomcs.state_store import WecomCSStateStore


class FakeRedisManager:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int | None] = {}

    def is_available(self) -> bool:
        return True

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str):
        self.values.pop(key, None)
        self.expirations.pop(key, None)

    async def set_if_not_exists(self, key: str, value: str, ex: int | None = None) -> bool:
        if key in self.values:
            return False
        self.values[key] = value
        self.expirations[key] = ex
        return True


class FakeWecomClient:
    def __init__(self):
        self.pages = {
            None: {
                'msg_list': [
                    {'msgid': 'msg-1', 'msgtype': 'text'},
                    {'msgid': 'msg-2', 'msgtype': 'text'},
                ],
                'next_cursor': 'cursor-2',
                'has_more': True,
            },
            'cursor-2': {
                'msg_list': [
                    {'msgid': 'msg-3', 'msgtype': 'text'},
                ],
                'next_cursor': 'cursor-3',
                'has_more': False,
            },
        }

    async def fetch_sync_msg_page(self, callback_token: str, open_kfid: str, cursor: str | None = None):
        return self.pages[cursor]


@pytest.mark.asyncio
async def test_pull_worker_processes_all_pages_and_updates_cursor():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='replay')
    client = FakeWecomClient()
    handled_messages: list[str] = []

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
        }
    )

    assert processed_count == 3
    assert handled_messages == ['msg-1', 'msg-2', 'msg-3']
    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-3'


@pytest.mark.asyncio
async def test_pull_worker_skips_duplicates_using_state_store():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='replay')
    client = FakeWecomClient()
    handled_messages: list[str] = []

    await store.reserve_message_for_queue('bot-1', 'kf-1', {'msgid': 'msg-1', 'external_userid': 'user-1', 'msgtype': 'text'})

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
        }
    )

    assert processed_count == 2
    assert handled_messages == ['msg-2', 'msg-3']


@pytest.mark.asyncio
async def test_pull_worker_does_not_requeue_failed_message_from_state_store():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='replay')
    client = FakeWecomClient()
    handled_messages: list[str] = []

    await store.reserve_message_for_queue('bot-1', 'kf-1', {'msgid': 'msg-1', 'external_userid': 'user-1', 'msgtype': 'text'})
    await store.mark_message_failed('bot-1', 'kf-1', 'msg-1', stage='reply_message', error='boom')

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
        }
    )

    assert processed_count == 2
    assert handled_messages == ['msg-2', 'msg-3']


@pytest.mark.asyncio
async def test_pull_worker_raises_when_lock_not_acquired():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='replay')
    client = FakeWecomClient()

    await store.acquire_pull_lock('bot-1', 'kf-1', 'other-owner', 60)

    async def on_message(message_data: dict):
        raise AssertionError('on_message should not be called when lock is not acquired')

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)

    with pytest.raises(PullLockNotAcquiredError):
        await worker.handle_trigger(
            {
                'bot_uuid': 'bot-1',
                'open_kfid': 'kf-1',
                'callback_token': 'token-1',
            }
        )


@pytest.mark.asyncio
async def test_pull_worker_bootstrap_latest_skips_history_and_updates_cursor():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='latest')
    client = FakeWecomClient()
    handled_messages: list[str] = []

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
        }
    )

    assert processed_count == 1
    assert handled_messages == ['msg-3']
    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-3'
    assert await store.is_bootstrapped('bot-1', 'kf-1') is True


@pytest.mark.asyncio
async def test_pull_worker_clears_stale_cursor_and_restarts_with_current_token():
    class InvalidCursorClient(FakeWecomClient):
        def __init__(self):
            super().__init__()
            self.calls: list[str | None] = []

        async def fetch_sync_msg_page(self, callback_token: str, open_kfid: str, cursor: str | None = None):
            self.calls.append(cursor)
            if cursor == 'stale-cursor':
                raise WecomCSInvalidSyncMsgTokenError('invalid msg token')
            return await super().fetch_sync_msg_page(callback_token, open_kfid, cursor)

    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='latest')
    client = InvalidCursorClient()
    handled_messages: list[str] = []

    await store.mark_bootstrapped('bot-1', 'kf-1', 'stale-cursor')

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(client, store, on_message, message_state_ttl_seconds=600, lock_ttl_seconds=60)
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'fresh-token',
        }
    )

    assert processed_count == 1
    assert handled_messages == ['msg-3']
    assert client.calls == ['stale-cursor', None, 'cursor-2']
    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-3'


@pytest.mark.asyncio
async def test_pull_worker_bootstrap_latest_drops_old_history_by_send_time_window():
    class WindowedClient:
        def __init__(self):
            self.pages = {
                None: {
                    'msg_list': [
                        {'msgid': 'old-1', 'msgtype': 'text', 'send_time': 700},
                    ],
                    'next_cursor': 'cursor-2',
                    'has_more': True,
                },
                'cursor-2': {
                    'msg_list': [
                        {'msgid': 'old-2', 'msgtype': 'text', 'send_time': 890},
                        {'msgid': 'recent-1', 'msgtype': 'text', 'send_time': 955},
                        {'msgid': 'recent-2', 'msgtype': 'text', 'send_time': 980},
                    ],
                    'next_cursor': 'cursor-3',
                    'has_more': False,
                },
            }

        async def fetch_sync_msg_page(self, callback_token: str, open_kfid: str, cursor: str | None = None):
            return self.pages[cursor]

    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='latest')
    client = WindowedClient()
    handled_messages: list[str] = []

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(
        client,
        store,
        on_message,
        message_state_ttl_seconds=600,
        lock_ttl_seconds=60,
        history_message_drop_threshold_seconds=60,
    )
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
            'webhook_received_at': '1000',
        }
    )

    assert processed_count == 2
    assert handled_messages == ['recent-1', 'recent-2']
    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-3'


@pytest.mark.asyncio
async def test_pull_worker_replay_mode_does_not_drop_messages_by_history_window():
    class ReplayClient:
        async def fetch_sync_msg_page(self, callback_token: str, open_kfid: str, cursor: str | None = None):
            return {
                'msg_list': [
                    {'msgid': 'old-1', 'msgtype': 'text', 'send_time': 700},
                    {'msgid': 'recent-1', 'msgtype': 'text', 'send_time': 980},
                ],
                'next_cursor': 'cursor-1',
                'has_more': False,
            }

    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, cursor_bootstrap_mode='replay')
    client = ReplayClient()
    handled_messages: list[str] = []

    async def on_message(message_data: dict):
        handled_messages.append(message_data['msgid'])

    worker = WecomCSPullWorker(
        client,
        store,
        on_message,
        message_state_ttl_seconds=600,
        lock_ttl_seconds=60,
        history_message_drop_threshold_seconds=60,
    )
    processed_count = await worker.handle_trigger(
        {
            'bot_uuid': 'bot-1',
            'open_kfid': 'kf-1',
            'callback_token': 'token-1',
            'webhook_received_at': '1000',
        }
    )

    assert processed_count == 2
    assert handled_messages == ['old-1', 'recent-1']
