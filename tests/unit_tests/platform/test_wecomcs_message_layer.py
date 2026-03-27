import pytest

from langbot.pkg.platform.wecomcs.message_publisher import WecomCSMessagePublisher
from langbot.pkg.platform.wecomcs.message_worker import WecomCSMessageWorker


class FakeRedisManager:
    def __init__(self):
        self.entries: list[tuple[str, dict[str, str]]] = []

    def is_available(self) -> bool:
        return True

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None):
        self.entries.append((stream, fields))
        return '1-0'


def test_message_publisher_routes_message_to_process_stream():
    redis_mgr = FakeRedisManager()
    publisher = WecomCSMessagePublisher(redis_mgr, shard_count=16)

    msg_data = {
        'open_kfid': 'kf-1',
        'external_userid': 'user-1',
        'msgid': 'msg-1',
        'msgtype': 'text',
        'send_time': 123456,
        'text': {'content': 'hello'},
    }

    import asyncio

    stream_name, payload = asyncio.run(publisher.publish_message('bot-1', msg_data))

    assert stream_name.startswith('wecomcs:bot-1:message-process:')
    assert payload['job_type'] == 'message_process'
    assert payload['external_userid'] == 'user-1'
    assert redis_mgr.entries[0][0] == stream_name


@pytest.mark.asyncio
async def test_message_worker_dispatches_to_client_handle_message():
    dispatched: list[str] = []

    class FakeClient:
        async def _handle_message(self, event):
            dispatched.append(event.message_id)

    worker = WecomCSMessageWorker(FakeClient())
    ok = await worker.handle_message(
        {
            'msgtype': 'text',
            'external_userid': 'user-1',
            'open_kfid': 'kf-1',
            'msgid': 'msg-1',
            'send_time': 111,
            'text': {'content': 'hello'},
        }
    )

    assert ok is True
    assert dispatched == ['msg-1']


@pytest.mark.asyncio
async def test_message_worker_returns_false_for_invalid_payload():
    class FakeClient:
        async def _handle_message(self, event):
            raise AssertionError('should not dispatch invalid payload')

    worker = WecomCSMessageWorker(FakeClient())
    ok = await worker.handle_message({'foo': 'bar'})

    assert ok is False


@pytest.mark.asyncio
async def test_message_worker_updates_state_for_success_and_failure():
    from langbot.pkg.platform.wecomcs.state_store import WecomCSStateStore

    class FakeRedisManagerWithJson(FakeRedisManager):
        def __init__(self):
            super().__init__()
            self.values = {}
            self.expirations = {}

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
            import json
            raw = self.values.get(key)
            return json.loads(raw) if raw else None

        async def set_json(self, key: str, value: dict, ex: int | None = None):
            import json
            self.values[key] = json.dumps(value, ensure_ascii=False)
            self.expirations[key] = ex

    redis_mgr = FakeRedisManagerWithJson()
    store = WecomCSStateStore(redis_mgr, message_state_ttl_seconds=600)
    await store.reserve_message_for_queue(
        'bot-1',
        'kf-1',
        {
            'msgid': 'msg-1',
            'external_userid': 'user-1',
            'msgtype': 'text',
            'text': {'content': 'hello'},
        },
    )

    class SuccessClient:
        async def _handle_message(self, event):
            return None

    worker = WecomCSMessageWorker(SuccessClient(), store, bot_uuid='bot-1')
    ok = await worker.handle_message(
        {
            'msgtype': 'text',
            'external_userid': 'user-1',
            'open_kfid': 'kf-1',
            'msgid': 'msg-1',
            'send_time': 111,
            'text': {'content': 'hello'},
        }
    )

    assert ok is True
    state = await store.get_message_state('bot-1', 'kf-1', 'msg-1')
    assert state['process_status'] == 'done'

    await store.reserve_message_for_queue(
        'bot-1',
        'kf-1',
        {
            'msgid': 'msg-2',
            'external_userid': 'user-2',
            'msgtype': 'text',
            'text': {'content': 'hello'},
        },
    )

    class FailedClient:
        async def _handle_message(self, event):
            raise RuntimeError('boom')

    worker = WecomCSMessageWorker(FailedClient(), store, bot_uuid='bot-1')
    with pytest.raises(RuntimeError):
        await worker.handle_message(
            {
                'msgtype': 'text',
                'external_userid': 'user-2',
                'open_kfid': 'kf-1',
                'msgid': 'msg-2',
                'send_time': 111,
                'text': {'content': 'hello'},
            }
        )

    state = await store.get_message_state('bot-1', 'kf-1', 'msg-2')
    assert state['process_status'] == 'failed'
