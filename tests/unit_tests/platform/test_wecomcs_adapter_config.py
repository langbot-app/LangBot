import pytest

import langbot.pkg.platform.sources.wecomcs as wecomcs_source
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.sources.wecomcs import WecomCSAdapter, WecomEventConverter


class FakeRedisManager:
    def is_available(self) -> bool:
        return True


class FakeInstanceConfig:
    def __init__(self, scheduler_config: dict):
        self.data = {'wecomcs_scheduler': scheduler_config}


class FakeApp:
    def __init__(self, scheduler_config: dict):
        self.instance_config = FakeInstanceConfig(scheduler_config)
        self.redis_mgr = FakeRedisManager()
        self.persistence_mgr = object()


class FakeLogger(abstract_platform_logger.AbstractEventLogger):
    def __init__(self, scheduler_config: dict):
        self.ap = FakeApp(scheduler_config)

    async def error(self, *args, **kwargs):
        return None

    async def warning(self, *args, **kwargs):
        return None

    async def info(self, *args, **kwargs):
        return None

    async def debug(self, *args, **kwargs):
        return None


@pytest.fixture
def base_config() -> dict:
    return {
        'corpid': 'corp-id',
        'secret': 'secret',
        'token': 'token',
        'EncodingAESKey': 'aes',
        'api_base_url': 'https://qyapi.weixin.qq.com/cgi-bin',
    }


@pytest.mark.asyncio
async def test_wecomcs_bot_config_overrides_global_scheduler_settings(base_config):
    logger = FakeLogger(
        {
            'enabled': True,
            'history_message_drop_threshold_seconds': 180,
            'retry_max_attempts': 7,
            'retry_backoff_seconds': [9, 18, 27],
            'lock_ttl_seconds': 99,
            'nickname_lookup_timeout_seconds': 5.0,
        }
    )
    adapter = WecomCSAdapter(
        {
            **base_config,
            'history_message_drop_threshold_seconds': 45,
            'retry_max_attempts': 2,
            'retry_backoff_seconds': '3,6,9',
            'lock_ttl_seconds': 12,
            'nickname_lookup_timeout_seconds': 1.25,
        },
        logger,
    )

    adapter.set_bot_uuid('bot-1')

    assert adapter.scheduler_runtime is not None
    assert adapter.scheduler_runtime.scheduler_config['pull_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['process_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['history_message_drop_threshold_seconds'] == 45
    assert adapter.scheduler_runtime.scheduler_config['retry_max_attempts'] == 2
    assert adapter.scheduler_runtime.scheduler_config['retry_backoff_seconds'] == [3, 6, 9]
    assert adapter.scheduler_runtime.scheduler_config['lock_ttl_seconds'] == 12
    assert adapter.bot.nickname_lookup_timeout_seconds == 1.25


@pytest.mark.asyncio
async def test_wecomcs_adapter_falls_back_to_global_scheduler_settings(base_config):
    logger = FakeLogger(
        {
            'enabled': True,
            'history_message_drop_threshold_seconds': 150,
            'retry_max_attempts': 5,
            'retry_backoff_seconds': [10, 20],
            'lock_ttl_seconds': 88,
            'nickname_lookup_timeout_seconds': 4.0,
        }
    )
    adapter = WecomCSAdapter(base_config, logger)

    adapter.set_bot_uuid('bot-1')

    assert adapter.scheduler_runtime is not None
    assert adapter.scheduler_runtime.scheduler_config['pull_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['process_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['history_message_drop_threshold_seconds'] == 150
    assert adapter.scheduler_runtime.scheduler_config['retry_max_attempts'] == 5
    assert adapter.scheduler_runtime.scheduler_config['retry_backoff_seconds'] == [10, 20]
    assert adapter.scheduler_runtime.scheduler_config['lock_ttl_seconds'] == 88
    assert adapter.bot.nickname_lookup_timeout_seconds == 4.0


@pytest.mark.asyncio
async def test_wecomcs_adapter_falls_back_to_code_defaults_when_configs_missing(base_config):
    logger = FakeLogger({'enabled': True})
    adapter = WecomCSAdapter(base_config, logger)

    adapter.set_bot_uuid('bot-1')

    assert adapter.scheduler_runtime is not None
    assert adapter.scheduler_runtime.scheduler_config['pull_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['process_stream_shard_count'] == 1
    assert adapter.scheduler_runtime.scheduler_config['history_message_drop_threshold_seconds'] == 90
    assert adapter.scheduler_runtime.scheduler_config['retry_max_attempts'] == 3
    assert adapter.scheduler_runtime.scheduler_config['retry_backoff_seconds'] == [15, 30, 45]
    assert adapter.scheduler_runtime.scheduler_config['lock_ttl_seconds'] == 60
    assert adapter.bot.nickname_lookup_timeout_seconds == 30.0


@pytest.mark.asyncio
async def test_wecomcs_adapter_uses_defaults_when_retry_backoff_string_invalid(base_config):
    logger = FakeLogger(
        {
            'enabled': True,
            'retry_backoff_seconds': [11, 22, 33],
        }
    )
    adapter = WecomCSAdapter(
        {
            **base_config,
            'retry_backoff_seconds': 'abc, ,x',
        },
        logger,
    )

    adapter.set_bot_uuid('bot-1')

    assert adapter.scheduler_runtime is not None
    assert adapter.scheduler_runtime.scheduler_config['retry_backoff_seconds'] == [11, 22, 33]


@pytest.mark.asyncio
async def test_target2yiri_uses_bot_configured_nickname_timeout(monkeypatch):
    captured = {}

    async def fake_wait_for(coro, timeout):
        captured['timeout'] = timeout
        result = await coro
        return result

    class FakeBot:
        nickname_lookup_timeout_seconds = 1.75

        async def get_customer_info(self, external_userid: str):
            return {'nickname': 'Tester'}

    class FakeEvent:
        type = 'text'
        user_id = 'user-1'
        message = 'hello'
        message_id = 'msg-1'
        timestamp = 123456
        receiver_id = 'kf-1'

    monkeypatch.setattr(wecomcs_source.asyncio, 'wait_for', fake_wait_for)

    result = await WecomEventConverter.target2yiri(FakeEvent(), FakeBot())

    assert captured['timeout'] == 1.75
    assert result.sender.nickname == 'Tester'
