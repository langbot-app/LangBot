"""Output attachments are explicitly submitted, never scanned by the wrapper."""

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, File
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
import pytest

from types import SimpleNamespace
from unittest.mock import AsyncMock

from tests.factories import FakeApp, text_query
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes


@pytest.mark.parametrize('cls', [Message, MessageChunk])
def test_explicit_output_attachments_survive_platform_conversion_only(cls):
    message = cls(role='assistant', content='done', attachments=MessageChain([File(name='result.txt', base64='YQ==')]))
    assert message.get_content_platform_message_chain()[-1].name == 'result.txt'
    assert 'attachments' not in message.model_dump()


@pytest.mark.parametrize('cls', [Message, MessageChunk])
def test_file_only_output(cls):
    message = cls(role='assistant', attachments=MessageChain([File(name='result.txt', base64='YQ==')]))
    assert len(message.get_content_platform_message_chain()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('cls', [Message, MessageChunk])
@pytest.mark.parametrize('content,with_file', [('answer', False), ('answer', True), ('', True)])
async def test_wrapper_delivers_explicit_files_without_scanning_box(cls, content, with_file):
    from langbot.pkg.pipeline.wrapper.wrapper import ResponseWrapper

    app = FakeApp()
    app.box_service = SimpleNamespace(available=True, collect_outbound_attachments=AsyncMock(return_value=[]))
    event = SimpleNamespace(reply_message_chain=None)
    app.plugin_connector.emit_event = AsyncMock(
        return_value=SimpleNamespace(event=event, is_prevented_default=lambda: False)
    )
    query = text_query('hello')
    query.pipeline_config = {
        'output': {'misc': {'at-sender': False, 'quote-origin': False, 'track-function-calls': False}}
    }
    message = cls(
        role='assistant',
        content=content,
        attachments=MessageChain([File(name='result.txt', base64='YQ==')]) if with_file else None,
    )
    if isinstance(message, MessageChunk):
        message.is_final = True
    query.resp_messages = [message]
    query.resp_message_chain = []
    app.sess_mgr.get_session = AsyncMock(
        return_value=Session(
            launcher_type=LauncherTypes.PERSON,
            launcher_id=12345,
            sender_id=12345,
            use_prompt_name='default',
            using_conversation=None,
            conversations=[],
        )
    )
    stage = ResponseWrapper(app)
    results = [result async for result in stage.process(query, 'ResponseWrapper')]
    assert results
    if with_file:
        assert query.resp_message_chain[-1][-1].name == 'result.txt'
    app.box_service.collect_outbound_attachments.assert_not_awaited()
