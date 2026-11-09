"""One ordered media list drives model contents, attachments and reads by ref."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.agent.runner import input_media
from langbot.pkg.box.runner import input_files, prepare_input_files

IMAGE_URL = 'https://wework.qpic.cn/image.jpg'
IMAGE_BASE64 = 'data:image/jpeg;base64,/9j/AAAA'
REPORT_BASE64 = base64.b64encode(b'%PDF report').decode()


def _chain(*components):
    return platform_message.MessageChain(list(components))


def _texts(contents):
    return [(item.type, item.text) for item in contents]


def test_markers_place_each_media_and_attachments_are_metadata_only():
    rendered = input_media.render_input(
        _chain(
            platform_message.Plain(text='compare '),
            platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64),
            platform_message.Plain(text=' with '),
            platform_message.File(name='report.pdf', base64=REPORT_BASE64, size=11),
        ),
        include_quotes=True,
    )

    assert rendered.text == 'compare [attachment att-1: image] with [attachment att-2: file report.pdf]'
    assert [item.type for item in rendered.contents] == ['text', 'text', 'image_base64', 'text', 'text', 'file_base64']
    assert rendered.plain_text == 'compare  with '
    assert rendered.attachments() == [
        {
            'ref': 'att-1',
            'type': 'image',
            'source': 'message',
            'name': None,
            'mime_type': 'image/jpeg',
            'size': None,
            'id': None,
            'url': IMAGE_URL,
        },
        {
            'ref': 'att-2',
            'type': 'file',
            'source': 'message',
            'name': 'report.pdf',
            'mime_type': 'application/pdf',
            'size': 11,
            'id': None,
            'url': None,
        },
    ]


def test_quoted_media_are_wrapped_and_marked_as_quote():
    quote = platform_message.Quote(
        sender_id='alice',
        origin=_chain(platform_message.Plain(text='see this'), platform_message.Image(url=IMAGE_URL)),
    )
    chain = _chain(quote, platform_message.Plain(text='what is it?'))

    rendered = input_media.render_input(chain, include_quotes=True)

    assert rendered.text == (
        '[quoted message from alice]\nsee this[attachment att-1: image]\n[/quoted message]what is it?'
    )
    assert [item.origin for item in rendered.media] == ['quote']
    assert rendered.attachments()[0]['source'] == 'quote'
    # Quoted text stays out of the pipeline's plain user_message_text variable.
    assert rendered.plain_text == 'what is it?'
    assert input_media.render_input(chain, include_quotes=False).media == []


def test_empty_quote_and_text_only_models_render_without_payloads():
    rendered = input_media.render_input(
        _chain(
            platform_message.Quote(origin=_chain()),
            platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64),
        ),
        include_quotes=True,
        keep_images=False,
    )

    assert _texts(rendered.contents) == [('text', '[attachment att-1: image]')]
    assert rendered.plain_text == '[Image]'
    assert [item.ref for item in rendered.media] == ['att-1']


def test_event_first_input_hands_payloads_to_the_run_registry_only():
    from langbot.pkg.platform.botmgr import RuntimeBot

    event = SimpleNamespace(
        message_chain=_chain(
            platform_message.Plain(text='look'),
            platform_message.Image(base64=IMAGE_BASE64),
        )
    )
    agent_input = RuntimeBot._build_agent_input(event)

    assert agent_input.text == 'look[attachment att-1: image]'
    assert agent_input.attachments[0].content == IMAGE_BASE64

    # Event runs execute against a text-only chain; the envelope payload is registered by ref.
    query = SimpleNamespace(message_chain=_chain(platform_message.Plain(text=agent_input.text)))
    prepare_input_files(query, agent_input)

    assert agent_input.attachments[0].ref == 'att-1'
    assert agent_input.attachments[0].content is None
    assert input_files(query)['att-1'].base64 == IMAGE_BASE64


@pytest.mark.asyncio
async def test_id_only_media_resolve_through_the_adapter_file_url(monkeypatch):
    downloads = []

    async def download(url, max_bytes):
        downloads.append(url)
        return b'file', 'application/pdf'

    monkeypatch.setattr(input_media, '_download', download)
    adapter = SimpleNamespace(get_file_url=AsyncMock(return_value='https://files.example/media-1'))

    resolved = await input_media.read_component_bytes(platform_message.File(id='media-1'), adapter=adapter)

    assert resolved == (b'file', 'application/pdf')
    adapter.get_file_url.assert_awaited_once_with('media-1')
    assert downloads == ['https://files.example/media-1']
    assert await input_media.read_component_bytes(platform_message.File(id='media-1')) is None


class _Handler:
    def __init__(self):
        self.actions = {}
        self.ap = SimpleNamespace(logger=SimpleNamespace(debug=lambda *args, **kwargs: None))

    def action(self, name):
        def register(func):
            self.actions[name] = func
            return func

        return register

    async def _require_plugin_action_context(self):
        return SimpleNamespace(), None


@pytest.fixture
def read_action(monkeypatch):
    from langbot.pkg.plugin import handler as plugin_handler
    from langbot.pkg.plugin import input_attachment_actions

    query = SimpleNamespace(
        message_chain=_chain(
            platform_message.File(name='report.pdf', base64=REPORT_BASE64),
            platform_message.Image(url='https://example.invalid/i.png'),
        )
    )
    authorized = AsyncMock(return_value=({'run_id': 'run-1'}, None))
    monkeypatch.setattr(input_attachment_actions, '_validate_agent_run_session', authorized)
    monkeypatch.setattr(plugin_handler, '_resolve_action_query', lambda *args: query)
    h = _Handler()
    input_attachment_actions.register(h)
    return h.actions[PluginToRuntimeAction.READ_INPUT_ATTACHMENT], query, authorized


@pytest.mark.asyncio
async def test_read_action_returns_bytes_of_the_runs_own_media(read_action):
    action, query, authorized = read_action

    response = await action({'run_id': 'run-1', 'ref': 'att-1', 'caller_plugin_identity': 'p'})

    assert response.code == 0
    assert response.data == {
        'ref': 'att-1',
        'name': 'report.pdf',
        'mime_type': 'application/octet-stream',
        'size': len(b'%PDF report'),
        'content': REPORT_BASE64,
    }
    assert authorized.await_args.kwargs['api_capability'] == 'input_attachments'
    assert query._input_attachment_read_bytes == len(b'%PDF report')

    unknown = await action({'run_id': 'run-1', 'ref': 'att-9'})
    assert unknown.code != 0 and 'Unknown input attachment' in unknown.message


@pytest.mark.asyncio
async def test_read_action_enforces_the_run_budget(read_action):
    action, query, _ = read_action
    object.__setattr__(query, '_input_attachment_read_bytes', input_media.MAX_RUN_READ_BYTES)

    response = await action({'run_id': 'run-1', 'ref': 'att-1'})

    assert response.code != 0 and 'budget' in response.message


def test_steering_items_do_not_expose_refs_of_another_input():
    from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator

    event = SimpleNamespace(
        event_id='e',
        event_type='message.received',
        event_time=None,
        source='platform',
        source_event_type='message.received',
        raw_ref=None,
        data={},
        conversation_id='c',
        thread_id=None,
        bot_id='b',
        workspace_id='w',
        actor=None,
        subject=None,
        input=AgentInput(text='x', attachments=[InputAttachment(ref='att-1', type='image', url=IMAGE_URL)]),
    )

    item = AgentRunOrchestrator._build_steering_item(object(), event, 'run', 'runner')

    assert item['input']['attachments'][0]['ref'] is None
    assert item['input']['attachments'][0]['url'] == IMAGE_URL
