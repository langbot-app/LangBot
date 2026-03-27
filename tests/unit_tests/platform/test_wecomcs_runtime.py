import pytest

from langbot.libs.wecom_customer_service_api.api import WecomCSInvalidSyncMsgTokenError
from langbot.pkg.platform.wecomcs.runtime import WecomCSSchedulerRuntime


class FakeRedisManager:
    def __init__(self):
        self.key_prefix = 'langbot'
        self.groups: list[tuple[str, str]] = []
        self.xreadgroup_calls: list[tuple[str, str, dict[str, str]]] = []
        self.acks: list[tuple[str, str, str]] = []
        self.pull_messages = [
            (
                'langbot:wecomcs:bot-1:pull-trigger:0',
                [
                    ('1-0', {'bot_uuid': 'bot-1', 'open_kfid': 'kf-1', 'callback_token': 'token-1'}),
                ],
            )
        ]
        self.process_messages = [
            (
                'langbot:wecomcs:bot-1:message-process:0',
                [
                    ('2-0', {'payload': '{"msgtype":"text","external_userid":"user-1","open_kfid":"kf-1","msgid":"msg-1","send_time":111,"text":{"content":"hello"}}'}),
                ],
            )
        ]

    def is_available(self):
        return True

    async def xgroup_create(self, stream: str, group: str, id: str = '0', mkstream: bool = True):
        self.groups.append((stream, group))

    async def xreadgroup(self, group: str, consumer: str, streams: dict[str, str], count=None, block_ms=None):
        self.xreadgroup_calls.append((group, consumer, streams))
        if group == 'pull-group:bot-1' and self.pull_messages:
            return [self.pull_messages.pop(0)]
        if group == 'process-group:bot-1' and self.process_messages:
            return [self.process_messages.pop(0)]
        return []

    async def xack(self, stream: str, group: str, message_id: str):
        self.acks.append((stream, group, message_id))


@pytest.mark.asyncio
async def test_runtime_initializes_consumer_groups():
    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=object(),
        redis_mgr=FakeRedisManager(),
        scheduler_config={
            'pull_stream_shard_count': 2,
            'process_stream_shard_count': 3,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
        },
    )

    await runtime.initialize()

    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1') in runtime.redis_mgr.groups
    assert ('wecomcs:bot-1:pull-trigger:1', 'pull-group:bot-1') in runtime.redis_mgr.groups
    assert ('wecomcs:bot-1:message-process:2', 'process-group:bot-1') in runtime.redis_mgr.groups


@pytest.mark.asyncio
async def test_runtime_pull_loop_handles_and_acks_messages(monkeypatch):
    redis_mgr = FakeRedisManager()

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
        },
    )

    handled = []

    async def fake_handle_trigger(payload):
        handled.append(payload)
        runtime.running = False
        return 1

    runtime.pull_worker.handle_trigger = fake_handle_trigger
    runtime.running = True
    await runtime._run_pull_loop()

    assert handled[0]['open_kfid'] == 'kf-1'
    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1', '1-0') in redis_mgr.acks


@pytest.mark.asyncio
async def test_runtime_process_loop_handles_and_acks_messages():
    redis_mgr = FakeRedisManager()

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
        },
    )

    async def fake_handle_stream_entry(fields):
        runtime.running = False
        return True

    runtime.message_worker.handle_stream_entry = fake_handle_stream_entry
    runtime.running = True
    await runtime._run_process_loop()

    assert ('wecomcs:bot-1:message-process:0', 'process-group:bot-1', '2-0') in redis_mgr.acks


@pytest.mark.asyncio
async def test_runtime_pull_loop_schedules_retry_and_acks_on_failure():
    redis_mgr = FakeRedisManager()

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
            'retry_backoff_seconds': [1],
            'retry_max_attempts': 3,
        },
    )

    scheduled = []

    async def fake_schedule_retry(target_stream, fields, retry_count=0, error=''):
        scheduled.append((target_stream, fields, error))
        runtime.running = False
        return True

    async def fake_handle_trigger(payload):
        raise RuntimeError('pull failed')

    runtime.retry_scheduler.schedule_retry = fake_schedule_retry
    runtime.pull_worker.handle_trigger = fake_handle_trigger
    runtime.running = True
    await runtime._run_pull_loop()

    assert scheduled[0][0] == 'wecomcs:bot-1:pull-trigger:0'
    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1', '1-0') in redis_mgr.acks


@pytest.mark.asyncio
async def test_runtime_pull_loop_uses_retry_count_from_stream_fields_on_failure():
    redis_mgr = FakeRedisManager()
    redis_mgr.pull_messages = [
        (
            'langbot:wecomcs:bot-1:pull-trigger:0',
            [
                ('1-0', {'bot_uuid': 'bot-1', 'open_kfid': 'kf-1', 'callback_token': 'token-1', 'retry_count': '2'}),
            ],
        )
    ]

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
            'retry_backoff_seconds': [1],
            'retry_max_attempts': 5,
        },
    )

    scheduled = []

    async def fake_schedule_retry(target_stream, fields, retry_count=0, error=''):
        scheduled.append((target_stream, fields, retry_count, error))
        runtime.running = False
        return True

    async def fake_handle_trigger(payload):
        raise RuntimeError('pull failed again')

    runtime.retry_scheduler.schedule_retry = fake_schedule_retry
    runtime.pull_worker.handle_trigger = fake_handle_trigger
    runtime.running = True
    await runtime._run_pull_loop()

    assert scheduled[0][0] == 'wecomcs:bot-1:pull-trigger:0'
    assert scheduled[0][2] == 2
    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1', '1-0') in redis_mgr.acks


@pytest.mark.asyncio
async def test_runtime_retry_loop_replays_due_jobs_and_stops():
    redis_mgr = FakeRedisManager()

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'retry_poll_interval_seconds': 1,
        },
    )

    replay_calls = []

    async def fake_replay_due_jobs():
        replay_calls.append('called')
        runtime.running = False
        return 1

    runtime.retry_scheduler.replay_due_jobs = fake_replay_due_jobs
    runtime.running = True
    await runtime._run_retry_loop()

    assert replay_calls == ['called']


@pytest.mark.asyncio
async def test_runtime_pull_loop_does_not_retry_invalid_sync_msg_token():
    redis_mgr = FakeRedisManager()

    class FakeClient:
        pass

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=FakeClient(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
            'retry_backoff_seconds': [1],
            'retry_max_attempts': 3,
        },
    )

    scheduled = []

    async def fake_schedule_retry(target_stream, fields, retry_count=0, error=''):
        scheduled.append((target_stream, fields, retry_count, error))
        return True

    async def fake_handle_trigger(payload):
        runtime.running = False
        raise WecomCSInvalidSyncMsgTokenError('invalid msg token')

    runtime.retry_scheduler.schedule_retry = fake_schedule_retry
    runtime.pull_worker.handle_trigger = fake_handle_trigger
    runtime.running = True
    await runtime._run_pull_loop()

    assert scheduled == []
    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1', '1-0') in redis_mgr.acks


@pytest.mark.asyncio
async def test_runtime_pull_loop_skips_foreign_bot_message():
    redis_mgr = FakeRedisManager()
    redis_mgr.pull_messages = [
        (
            'langbot:wecomcs:bot-1:pull-trigger:0',
            [
                ('1-0', {'bot_uuid': 'bot-2', 'open_kfid': 'kf-1', 'callback_token': 'token-1'}),
            ],
        )
    ]

    runtime = WecomCSSchedulerRuntime(
        'bot-1',
        client=object(),
        redis_mgr=redis_mgr,
        scheduler_config={
            'pull_stream_shard_count': 1,
            'process_stream_shard_count': 1,
            'pull_consumer_group': 'pull-group',
            'process_consumer_group': 'process-group',
            'stream_batch_size': 1,
            'stream_block_ms': 1,
        },
    )

    called = False

    async def fake_handle_trigger(payload):
        nonlocal called
        called = True
        runtime.running = False
        return 1

    runtime.pull_worker.handle_trigger = fake_handle_trigger

    async def fake_xreadgroup(group, consumer, streams, count=None, block_ms=None):
        result = await FakeRedisManager.xreadgroup(redis_mgr, group, consumer, streams, count=count, block_ms=block_ms)
        runtime.running = False
        return result

    redis_mgr.xreadgroup = fake_xreadgroup
    runtime.running = True
    await runtime._run_pull_loop()

    assert called is False
    assert ('wecomcs:bot-1:pull-trigger:0', 'pull-group:bot-1', '1-0') in redis_mgr.acks
