import json

import pytest

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

    async def get_json(self, key: str):
        raw = self.values.get(key)
        if not raw:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: dict, ex: int | None = None):
        self.values[key] = json.dumps(value, ensure_ascii=False)
        self.expirations[key] = ex


class FakeCursorStore:
    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    async def get_checkpoint(self, bot_uuid: str, open_kfid: str):
        return self.items.get((bot_uuid, open_kfid))

    async def save_checkpoint(self, bot_uuid: str, open_kfid: str, cursor: str, bootstrapped: bool):
        self.items[(bot_uuid, open_kfid)] = {
            'bot_uuid': bot_uuid,
            'open_kfid': open_kfid,
            'cursor': cursor,
            'bootstrapped': bootstrapped,
        }


@pytest.mark.asyncio
async def test_state_store_persists_cursor_in_cursor_store():
    redis_mgr = FakeRedisManager()
    cursor_store = FakeCursorStore()
    store = WecomCSStateStore(redis_mgr, cursor_store=cursor_store)

    await store.set_cursor('bot-1', 'kf-1', 'cursor-1')

    assert await store.get_cursor('bot-1', 'kf-1') == 'cursor-1'
    assert await store.is_bootstrapped('bot-1', 'kf-1') is True


@pytest.mark.asyncio
async def test_state_store_tracks_message_status_with_ttl():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, message_state_ttl_seconds=123)

    reserved = await store.reserve_message_for_queue(
        'bot-1',
        'kf-1',
        {
            'msgid': 'msg-1',
            'external_userid': 'user-1',
            'msgtype': 'text',
            'send_time': 111,
            'text': {'content': 'hello world'},
        },
    )

    assert reserved is True
    state = await store.get_message_state('bot-1', 'kf-1', 'msg-1')
    assert state['process_status'] == 'queued'
    assert redis_mgr.expirations['wecomcs:msg:bot-1:kf-1:msg-1'] == 123

    await store.mark_message_processing('bot-1', 'kf-1', 'msg-1')
    await store.mark_message_done('bot-1', 'kf-1', 'msg-1')
    await store.mark_reply_success('bot-1', 'kf-1', 'msg-1')

    state = await store.get_message_state('bot-1', 'kf-1', 'msg-1')
    assert state['process_status'] == 'done'
    assert state['reply_status'] == 'success'


@pytest.mark.asyncio
async def test_state_store_rejects_failed_message_from_pull_requeue():
    redis_mgr = FakeRedisManager()
    store = WecomCSStateStore(redis_mgr, message_state_ttl_seconds=123)

    await store.reserve_message_for_queue(
        'bot-1',
        'kf-1',
        {
            'msgid': 'msg-1',
            'external_userid': 'user-1',
            'msgtype': 'text',
        },
    )
    await store.mark_message_failed('bot-1', 'kf-1', 'msg-1', stage='publish', error='boom')

    reserved = await store.reserve_message_for_queue(
        'bot-1',
        'kf-1',
        {
            'msgid': 'msg-1',
            'external_userid': 'user-1',
            'msgtype': 'text',
        },
    )

    assert reserved is False
    state = await store.get_message_state('bot-1', 'kf-1', 'msg-1')
    assert state['process_status'] == 'failed'
    assert state['last_error_stage'] == 'publish'
