"""Output attachments are explicitly submitted, never scanned by the wrapper."""

from langbot_plugin.api.entities.builtin.platform.message import MessageChain, File
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
import pytest


@pytest.mark.parametrize('cls', [Message, MessageChunk])
def test_explicit_output_attachments_survive_platform_conversion_only(cls):
    message = cls(role='assistant', content='done', attachments=MessageChain([File(name='result.txt', base64='YQ==')]))
    assert message.get_content_platform_message_chain()[-1].name == 'result.txt'
    assert 'attachments' not in message.model_dump()


@pytest.mark.parametrize('cls', [Message, MessageChunk])
def test_file_only_output(cls):
    message = cls(role='assistant', attachments=MessageChain([File(name='result.txt', base64='YQ==')]))
    assert len(message.get_content_platform_message_chain()) == 1
