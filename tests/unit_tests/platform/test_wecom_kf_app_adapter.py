import yaml
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger

from langbot.pkg.api.http.service.bot import BotService


def test_wecom_kf_app_adapter_inherits_wecomcs_adapter():
    from langbot.pkg.platform.sources.wecom_kf_app import WecomKFAppAdapter
    from langbot.pkg.platform.sources.wecomcs import WecomCSAdapter

    assert issubclass(WecomKFAppAdapter, WecomCSAdapter)


def test_wecom_kf_app_manifest_points_to_adapter_class():
    with open('src/langbot/pkg/platform/sources/wecom_kf_app.yaml', encoding='utf-8') as fp:
        data = yaml.safe_load(fp)

    assert data['metadata']['name'] == 'wecom_kf_app'
    assert data['execution']['python']['path'] == './wecom_kf_app.py'
    assert data['execution']['python']['attr'] == 'WecomKFAppAdapter'


class FakePlatformManager:
    async def get_bot_by_uuid(self, bot_uuid: str):
        return None


class FakeBotService(BotService):
    async def get_bot(self, bot_uuid: str, include_secret: bool = True):
        return {
            'uuid': bot_uuid,
            'adapter': 'wecom_kf_app',
            'adapter_config': {},
            'name': 'demo',
            'description': 'demo',
            'enable': True,
        }


class FakeApp:
    def __init__(self):
        self.platform_mgr = FakePlatformManager()
        self.instance_config = type(
            'Cfg',
            (),
            {'data': {'api': {'webhook_prefix': 'http://127.0.0.1:5300', 'extra_webhook_prefix': ''}}},
        )()


async def test_get_runtime_bot_info_exposes_webhook_url_for_wecom_kf_app():
    service = FakeBotService(FakeApp())

    runtime_info = await service.get_runtime_bot_info('bot-1')

    assert runtime_info['adapter_runtime_values']['webhook_url'] == '/bots/bot-1'
    assert runtime_info['adapter_runtime_values']['webhook_full_url'] == 'http://127.0.0.1:5300/bots/bot-1'


class FakeRedisManager:
    def is_available(self) -> bool:
        return True


class FakeInstanceConfig:
    def __init__(self):
        self.data = {'wecomcs_scheduler': {'enabled': True}}


class FakeAdapterApp:
    def __init__(self):
        self.instance_config = FakeInstanceConfig()
        self.redis_mgr = FakeRedisManager()
        self.persistence_mgr = object()


class FakeLogger(abstract_platform_logger.AbstractEventLogger):
    def __init__(self):
        self.ap = FakeAdapterApp()

    async def error(self, *args, **kwargs):
        return None

    async def warning(self, *args, **kwargs):
        return None

    async def info(self, *args, **kwargs):
        return None

    async def debug(self, *args, **kwargs):
        return None


def test_wecom_kf_app_adapter_creates_wecomcs_client():
    from langbot.libs.wecom_customer_service_api.api import WecomCSClient
    from langbot.pkg.platform.sources.wecom_kf_app import WecomKFAppAdapter

    adapter = WecomKFAppAdapter(
        {
            'corpid': 'corp-id',
            'secret': 'secret',
            'token': 'token',
            'EncodingAESKey': 'aes',
            'api_base_url': 'https://qyapi.weixin.qq.com/cgi-bin',
        },
        FakeLogger(),
    )

    assert isinstance(adapter.bot, WecomCSClient)
