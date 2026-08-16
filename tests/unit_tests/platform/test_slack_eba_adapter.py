from __future__ import annotations

import datetime
import pathlib
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from langbot.libs.slack_api.slackevent import SlackEvent
from langbot.pkg.platform.adapters.slack.adapter import SlackAdapter
from langbot.pkg.platform.adapters.slack.errors import NotSupportedError
from langbot.pkg.platform.adapters.slack.event_converter import SlackEventConverter
from langbot.pkg.platform.adapters.slack.message_converter import SlackMessageConverter
from langbot.pkg.platform.adapters.slack.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class DummyLogger(AbstractEventLogger):
    async def info(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def debug(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def warning(self, text, images=None, message_session_id=None, no_throw=True):
        pass

    async def error(self, text, images=None, message_session_id=None, no_throw=True):
        pass


class DummySlackWebClient:
    async def auth_test(self):
        return {'ok': True, 'user_id': 'B-1'}


class DummySlackClient:
    def __init__(self, *args, **kwargs):
        self.bot_token = kwargs['bot_token']
        self.signing_secret = kwargs['signing_secret']
        self.unified_mode = kwargs['unified_mode']
        self._message_handlers = {}
        self.client = DummySlackWebClient()
        self.sent = []
        self.handle_unified_webhook = AsyncMock(return_value='ok')

    def on_message(self, msg_type: str):
        def decorator(func):
            self._message_handlers.setdefault(msg_type, []).append(func)
            return func

        return decorator

    async def send_message_to_channel(self, text: str, channel_id: str):
        self.sent.append(('channel', channel_id, text))
        return {'ok': True, 'channel': channel_id, 'message': {'ts': '1.1'}}

    async def send_message_to_one(self, text: str, user_id: str):
        self.sent.append(('person', user_id, text))
        return {'ok': True, 'channel': user_id, 'message': {'ts': '1.2'}}


def manifest() -> dict:
    manifest_path = (
        pathlib.Path(__file__).parents[3]
        / 'src'
        / 'langbot'
        / 'pkg'
        / 'platform'
        / 'adapters'
        / 'slack'
        / 'manifest.yaml'
    )
    return yaml.safe_load(manifest_path.read_text())


def make_adapter() -> SlackAdapter:
    config = {
        'bot_token': 'xoxb-token',
        'signing_secret': 'signing-secret',
        'bot_user_id': 'B-1',
    }
    with patch('langbot.pkg.platform.adapters.slack.adapter.SlackClient', DummySlackClient):
        return SlackAdapter(config, DummyLogger())


def slack_event(channel_type: str = 'im', **overrides) -> SlackEvent:
    text = overrides.get('text', 'hello')
    payload = {
        'event_id': overrides.get('event_id', 'evt-1'),
        'event': {
            'type': 'app_mention' if channel_type == 'channel' else 'message',
            'channel_type': channel_type,
            'user': overrides.get('user_id', 'U-1'),
            'channel': overrides.get('channel_id', 'C-1'),
            'ts': overrides.get('ts', '1710003600.000100'),
            'event_ts': overrides.get('ts', '1710003600.000100'),
            'blocks': [
                {
                    'type': 'rich_text',
                    'elements': [
                        {
                            'type': 'rich_text_section',
                            'elements': [
                                {'type': 'text', 'text': text},
                            ],
                        }
                    ],
                }
            ],
        },
    }
    if channel_type == 'im':
        payload['event']['blocks'] = [
            {
                'elements': [
                    {
                        'elements': [
                            {'type': 'text', 'text': text},
                        ]
                    }
                ]
            }
        ]
    if overrides.get('pic_url'):
        payload['event']['files'] = [{'url_private': overrides['pic_url']}]
    return SlackEvent(payload)


def test_slack_supported_events_match_manifest():
    assert make_adapter().get_supported_events() == manifest()['spec']['supported_events']


def test_slack_supported_apis_match_manifest():
    supported_apis = make_adapter().get_supported_apis()
    manifest_apis = manifest()['spec']['supported_apis']

    assert supported_apis == manifest_apis['required'] + manifest_apis['optional']


def test_slack_platform_api_map_matches_manifest():
    manifest_actions = {item['action'] for item in manifest()['spec']['platform_specific_apis']}

    assert set(PLATFORM_API_MAP) == manifest_actions


@pytest.mark.asyncio
async def test_slack_message_converter_maps_common_components_to_text():
    text = await SlackMessageConverter.yiri2target(
        platform_message.MessageChain(
            [
                platform_message.Source(id='msg-0', time=datetime.datetime.now()),
                platform_message.Plain(text='hi'),
                platform_message.At(target='U-2'),
                platform_message.AtAll(),
                platform_message.Image(url='https://example.test/a.png'),
                platform_message.File(name='a.txt'),
                platform_message.Quote(origin=platform_message.MessageChain([platform_message.Plain(text='quoted')])),
            ]
        )
    )

    assert 'hi' in text
    assert '<@U-2>' in text
    assert '<!channel>' in text
    assert 'https://example.test/a.png' in text
    assert 'a.txt' in text
    assert 'quoted' in text


@pytest.mark.asyncio
async def test_slack_event_converter_maps_private_group_and_platform_specific():
    private_event = await SlackEventConverter().target2yiri(slack_event('im'))
    group_event = await SlackEventConverter().target2yiri(slack_event('channel'))
    platform_event = await SlackEventConverter().target2yiri(slack_event('file_share'))

    assert isinstance(private_event, platform_events.MessageReceivedEvent)
    assert private_event.adapter_name == 'slack-eba'
    assert private_event.chat_type == platform_entities.ChatType.PRIVATE
    assert private_event.chat_id == 'U-1'
    assert str(private_event.message_chain) == 'hello'

    assert isinstance(group_event, platform_events.MessageReceivedEvent)
    assert group_event.chat_type == platform_entities.ChatType.GROUP
    assert group_event.chat_id == 'C-1'
    assert isinstance(group_event.message_chain[1], platform_message.At)

    assert isinstance(platform_event, platform_events.PlatformSpecificEvent)
    assert platform_event.action == 'slack.file_share'


@pytest.mark.asyncio
async def test_slack_adapter_dispatches_eba_and_legacy_and_caches_group_event():
    adapter = make_adapter()
    eba_calls: list[platform_events.Event] = []
    legacy_calls: list[platform_events.Event] = []

    async def eba_listener(event, adapter):
        eba_calls.append(event)

    async def legacy_listener(event, adapter):
        legacy_calls.append(event)

    adapter.register_listener(platform_events.MessageReceivedEvent, eba_listener)
    adapter.register_listener(platform_events.GroupMessage, legacy_listener)
    await adapter._handle_native_event(slack_event('channel'))

    assert len(eba_calls) == 1
    assert len(legacy_calls) == 1
    received = eba_calls[0]
    assert await adapter.get_message('group', 'C-1', 'evt-1') == received
    assert (await adapter.get_group_info('C-1')).id == 'C-1'
    assert (await adapter.get_group_member_info('C-1', 'U-1')).user.id == 'U-1'


@pytest.mark.asyncio
async def test_slack_send_reply_platform_api_and_unsupported():
    adapter = make_adapter()
    source_event = await SlackEventConverter().target2yiri(slack_event('im'))

    reply_result = await adapter.reply_message(source_event, platform_message.MessageChain([platform_message.Plain(text='reply')]))
    assert reply_result.message_id == 'evt-1'
    assert ('person', 'U-1', 'reply') in adapter.bot.sent

    await adapter.send_message('group', 'C-1', platform_message.MessageChain([platform_message.Plain(text='hello channel')]))
    assert ('channel', 'C-1', 'hello channel') in adapter.bot.sent

    assert await adapter.call_platform_api('get_mode', {}) == {
        'webhook': True,
        'bot_account_id': 'B-1',
    }
    assert await adapter.call_platform_api('auth_test', {}) == {'ok': True, 'user_id': 'B-1'}

    with pytest.raises(NotSupportedError):
        await adapter.call_platform_api('missing', {})
