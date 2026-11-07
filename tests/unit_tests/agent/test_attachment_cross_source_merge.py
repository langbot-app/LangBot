"""One platform media component must reach a Runner as one attachment descriptor."""

from types import SimpleNamespace

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider.message import ContentElement
from langbot_plugin.api.entities.builtin.runner.input import AgentInput, InputAttachment

from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.box.runner import input_files, prepare_input_files

IMAGE_URL = 'https://wework.qpic.cn/image.jpg'
IMAGE_BASE64 = 'data:image/jpeg;base64,/9j/AAAA'
OTHER_BASE64 = 'data:image/png;base64,YQ=='


def _query(*components):
    return SimpleNamespace(message_chain=platform_message.MessageChain(list(components)))


def _prepare(query, contents):
    attachments = QueryEntryAdapter._build_attachments(query, [content.model_dump() for content in contents])
    agent_input = AgentInput(
        contents=contents,
        attachments=[InputAttachment.model_validate(item) for item in attachments],
    )
    prepare_input_files(query, agent_input)
    return agent_input


def test_inline_contents_and_url_backed_chain_image_merge_into_one_attachment():
    # WeCom, OneBot and QQ adapters attach both the platform URL and the
    # downloaded bytes; preprocessing forwards only the bytes in contents.
    query = _query(platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64))
    contents = [ContentElement.from_image_base64(IMAGE_BASE64)]

    attachments = QueryEntryAdapter._build_attachments(query, [content.model_dump() for content in contents])

    assert attachments == [
        {'type': 'image', 'source': 'base64', 'content': IMAGE_BASE64, 'url': IMAGE_URL},
    ]


def test_runner_never_receives_a_reference_only_twin_of_a_url_backed_image():
    query = _query(platform_message.Plain(text='look'), platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64))
    contents = [ContentElement.from_text('look'), ContentElement.from_image_base64(IMAGE_BASE64)]

    agent_input = _prepare(query, contents)

    assert [item.model_dump(exclude_none=True) for item in agent_input.attachments] == [
        {'ref': 'attachment-0', 'type': 'image', 'source': 'base64', 'url': IMAGE_URL},
    ]
    # The inline payload stays in contents and the Box input keeps the original component.
    assert agent_input.contents[1].image_base64 == IMAGE_BASE64
    assert input_files(query)[0].base64 == IMAGE_BASE64


def test_url_contents_and_inline_chain_image_merge_into_one_attachment():
    # Event-first ingress forwards the URL in contents when a component has both.
    query = _query(platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64))
    contents = [{'type': 'image_url', 'image_url': {'url': IMAGE_URL}}]

    attachments = QueryEntryAdapter._build_attachments(query, contents)

    assert attachments == [
        {'type': 'image', 'source': 'url', 'url': IMAGE_URL, 'content': IMAGE_BASE64},
    ]


def test_repeated_and_distinct_images_remain_separate_attachments():
    query = _query(
        platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64),
        platform_message.Image(url=IMAGE_URL, base64=IMAGE_BASE64),
        platform_message.Image(base64=OTHER_BASE64),
    )
    contents = [
        ContentElement.from_image_base64(IMAGE_BASE64),
        ContentElement.from_image_base64(IMAGE_BASE64),
        ContentElement.from_image_base64(OTHER_BASE64),
    ]

    attachments = QueryEntryAdapter._build_attachments(query, [content.model_dump() for content in contents])

    assert [(item['content'], item.get('url')) for item in attachments] == [
        (IMAGE_BASE64, IMAGE_URL),
        (IMAGE_BASE64, IMAGE_URL),
        (OTHER_BASE64, None),
    ]


def test_message_chain_only_file_is_kept_with_its_platform_id():
    query = _query(platform_message.File(id='media-1', name='report.pdf'))

    attachments = QueryEntryAdapter._build_attachments(query, [])

    assert attachments == [
        {
            'type': 'file',
            'source': 'message_chain',
            'id': 'media-1',
            'name': 'report.pdf',
            'url': None,
            'content': None,
        }
    ]
